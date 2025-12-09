import socket
import struct
import os
import json
import time
from datetime import datetime
from PIL import Image

# =====================
# Configurações
# =====================
HOST = "0.0.0.0"
PORT = 5000
BASE_DIR = "imagens"
META_FILE = "metadata.json"
BUFFER_SIZE = 1024
TIMEOUT = 2.0

metadata = []

# logica stop and wait para udp

def rdt_send(sock, data_bytes, addr):
    """
    Envia dados (string ou binário) quebrando em pedaços
    e esperando ACK para cada pedaço.
    """
    # Se for string, codifica
    if isinstance(data_bytes, str):
        data_bytes = data_bytes.encode("utf-8")

    total_len = len(data_bytes)
    # Primeiro, avisa o tamanho total do que vai ser enviado
    # Protocolo simples: Envia tamanho -> Espera ACK -> Envia dados
    header = struct.pack("!I", total_len)
    sock.sendto(header, addr)
    
    # Espera ACK do tamanho
    try:
        sock.settimeout(TIMEOUT)
        data, _ = sock.recvfrom(1024)
        if data != b'ACK_SIZE':
            print(f"Erro no handshake de tamanho com {addr}")
            return
    except socket.timeout:
        print(f"Timeout esperando ACK do tamanho de {addr}")
        return

    # Agora envia os pedaços
    seq = 0
    offset = 0
    while offset < total_len:
        chunk = data_bytes[offset:offset + BUFFER_SIZE]
        
        # Pacote: [SEQ 4 bytes] + [DADOS]
        pacote = struct.pack("!I", seq) + chunk
        
        ack_recebido = False
        while not ack_recebido:
            try:
                sock.sendto(pacote, addr)
                
                # Espera ACK
                resp, _ = sock.recvfrom(1024) # ACK deve ser apenas o numero da seq (4 bytes)
                
                if len(resp) == 4:
                    ack_seq = struct.unpack("!I", resp)[0]
                    if ack_seq == seq:
                        ack_recebido = True
                        seq += 1
                        offset += len(chunk)
            except socket.timeout:
                print(f"Timeout pacote {seq}. Reenviando...")
    
    return True

def rdt_recv(sock):
    """
    Recebe dados confiáveis montando o buffer.
    Retorna (dados_bytes, endereço_remetente)
    """
    sock.settimeout(None) # Loop principal não pode ter timeout curto
    
    # 1. Recebe tamanho esperado
    try:
        data, addr = sock.recvfrom(1024)
    except:
        return None, None

    #garantir que é o header de tamanho
    if len(data) != 4:
        return data, addr

    total_size = struct.unpack("!I", data)[0]
    sock.sendto(b'ACK_SIZE', addr) # envia o ack confirmando o tamanho

    received_data = b""
    expected_seq = 0
    sock.settimeout(TIMEOUT) # Agora ativa timeout para a transferência

    while len(received_data) < total_size:
        try:
            pacote, _ = sock.recvfrom(BUFFER_SIZE + 4)
            
            # Extrai cabeçalho
            seq = struct.unpack("!I", pacote[:4])[0]
            content = pacote[4:]

            if seq == expected_seq:
                received_data += content
                # Envia ACK
                sock.sendto(struct.pack("!I", seq), addr)
                expected_seq += 1
                
                # Se pacote vazio (FIM) e já temos tudo, sai
                if not content and len(received_data) >= total_size:
                    break
            else:
                # Recebeu duplicado ou fora de ordem, reenvia ACK do anterior
                sock.sendto(struct.pack("!I", seq), addr)
                
        except socket.timeout:
            print("Timeout recebendo arquivo. Abortando.")
            return None, addr

    return received_data, addr

# =====================
# Auxiliares
# =====================

def carregar_metadata():
    if not os.path.exists(META_FILE):
        return []
    with open(META_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def salvar_metadata(meta):
    with open(META_FILE, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

def criar_thumbnail(path_origem, path_thumb, tamanho=(128, 128)):
    try:
        img = Image.open(path_origem)
        img.thumbnail(tamanho)
        img.save(path_thumb, "JPEG")
        return True
    except:
        return False

# =====================
# Handlers
# =====================

def processar_comando(sock, dados_bytes, addr):
    global metadata
    try:
        msg = dados_bytes.decode("utf-8").strip()
    except:
        return # Dados inválidos

    print(f"[{addr}] Comando: {msg}")
    parts = msg.split("|")
    cmd = parts[0].upper()

    # == UPLOAD ==
    if cmd == "UPLOAD": 
        # Formato: UPLOAD|filename|size|username
        if len(parts) < 3:
            rdt_send(sock, "ERROR|Formato invalido", addr)
            return

        filename = parts[1]
        tamanho = int(parts[2])
        username = parts[3] if len(parts) > 3 else "anon"

        rdt_send(sock, "READY", addr) # Avisa que pode mandar

        # Recebe o arquivo via RDT
        file_content, _ = rdt_recv(sock)
        
        if file_content:
            user_dir = os.path.join(BASE_DIR, username)
            os.makedirs(user_dir, exist_ok=True)
            filepath = os.path.join(user_dir, filename)
            
            with open(filepath, "wb") as f:
                f.write(file_content)

            # Thumbnail
            thumb_path = os.path.join(user_dir, f"thumb_{filename}")
            has_thumb = 1 if criar_thumbnail(filepath, thumb_path) else 0

            # Metadata
            metadata = carregar_metadata()
            metadata.append({
                "filename": filename,
                "author": username,
                "path": filepath,
                "thumb_path": thumb_path,
                "size": tamanho,
                "has_thumb": has_thumb,
                "datetime": datetime.now().isoformat(timespec="seconds")
            })
            salvar_metadata(metadata)
            rdt_send(sock, "OK|Upload concluido", addr)
        else:
            rdt_send(sock, "ERROR|Falha no recebimento", addr)

    # == LIST ==
    elif cmd == "LIST":
        metadata = carregar_metadata()
        lines = []
        for info in metadata:
            lines.append(f"{info['filename']}|{info['author']}|{info['datetime']}|{info['size']}|{info['has_thumb']}")
        
        full_text = "\n".join(lines) if lines else "EMPTY"
        rdt_send(sock, full_text, addr)

    # == DOWNLOAD ou VIEW ==
    elif cmd == "DOWNLOAD" or cmd == "VIEW":
        if len(parts) < 2: return
        filename = parts[1]
        
        metadata = carregar_metadata()
        info = next((m for m in metadata if m["filename"] == filename), None)
        
        target_path = ""
        if info:
            if cmd == "DOWNLOAD": target_path = info["path"]
            else: target_path = info["thumb_path"]

        if info and os.path.exists(target_path):
            size = os.path.getsize(target_path)
            rdt_send(sock, f"FOUND|{size}", addr)
            
            # Espera cliente confirmar
            resp, _ = rdt_recv(sock)
            if resp and resp.decode() == "READY":
                with open(target_path, "rb") as f:
                    content = f.read()
                rdt_send(sock, content, addr)
        else:
            rdt_send(sock, "ERROR|Arquivo nao encontrado", addr)

def main():
    os.makedirs(BASE_DIR, exist_ok=True)
    global metadata
    metadata = carregar_metadata()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((HOST, PORT))
    print(f"Servidor UDP ouvindo em {HOST}:{PORT}")

    while True:
        # Loop principal espera comandos iniciais
        # Nota: O rdt_recv é bloqueante, idealmente isso seria uma máquina de estados
        # mas para o trabalho, assumimos que o cliente inicia com um pacote de comando.
        dados, addr = rdt_recv(sock)
        if dados:
            processar_comando(sock, dados, addr)

if __name__ == "__main__":
    main()
