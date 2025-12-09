import socket
import os
import struct

HOST = "127.0.0.1"
PORT = 5000
TIMEOUT = 2.0
BUFFER_SIZE = 1024
DOWNLOAD_DIR = "downloads"


def rdt_send(sock, data_bytes, addr):
    if isinstance(data_bytes, str):
        data_bytes = data_bytes.encode("utf-8")

    total_len = len(data_bytes)
    header = struct.pack("!I", total_len)
    sock.sendto(header, addr)
    
    try:
        sock.settimeout(TIMEOUT)
        data, _ = sock.recvfrom(1024)
        if data != b'ACK_SIZE':
            return False
    except socket.timeout:
        return False

    seq = 0
    offset = 0
    while offset < total_len:
        chunk = data_bytes[offset:offset + BUFFER_SIZE]
        pacote = struct.pack("!I", seq) + chunk
        
        ack_recebido = False
        while not ack_recebido:
            try:
                sock.sendto(pacote, addr)
                resp, _ = sock.recvfrom(1024)
                if len(resp) == 4:
                    ack_seq = struct.unpack("!I", resp)[0]
                    if ack_seq == seq:
                        ack_recebido = True
                        seq += 1
                        offset += len(chunk)
            except socket.timeout:
                pass #reenvia o pacote
    return True

def rdt_recv(sock):
    sock.settimeout(TIMEOUT)
    try:
        data, addr = sock.recvfrom(1024)
    except socket.timeout:
        return None
        
    if len(data) != 4: return None
    
    total_size = struct.unpack("!I", data)[0]
    sock.sendto(b'ACK_SIZE', addr)

    received_data = b""
    expected_seq = 0
    
    while len(received_data) < total_size:
        try:
            pacote, server_addr = sock.recvfrom(BUFFER_SIZE + 4)
            seq = struct.unpack("!I", pacote[:4])[0]
            content = pacote[4:]

            if seq == expected_seq:
                received_data += content
                sock.sendto(struct.pack("!I", seq), server_addr)
                expected_seq += 1
                if not content and len(received_data) >= total_size: break
            else:
                sock.sendto(struct.pack("!I", seq), server_addr)
        except socket.timeout:
            break

    return received_data

# Comandos


def cmd_upload(sock, server_addr, username):
    path = input("Caminho da imagem: ").strip()
    if not os.path.exists(path):
        print("Arquivo não existe.")
        return

    filename = os.path.basename(path)
    size = os.path.getsize(path)
    
    # Envia comando
    cmd = f"UPLOAD|{filename}|{size}|{username}"
    print("Enviando solicitação...")
    if not rdt_send(sock, cmd, server_addr):
        print("Servidor não respondeu.")
        return

    resp = rdt_recv(sock)
    if resp and resp.decode() == "READY":
        print("Enviando arquivo...")
        with open(path, "rb") as f:
            content = f.read()
        rdt_send(sock, content, server_addr)
        
        final_msg = rdt_recv(sock)
        print("Servidor:", final_msg.decode() if final_msg else "Sem confirmação final")
    else:
        print("Erro: Servidor recusou upload")

def cmd_list(sock, server_addr):
    rdt_send(sock, "LIST", server_addr)
    data = rdt_recv(sock)
    if data:
        text = data.decode("utf-8")
        if text == "EMPTY":
            print("Nenhuma imagem.")
        else:
            print("\n=== Imagens Disponíveis ===")
            print(f"{'Arquivo':<20} | {'Autor':<10} | {'Data':<20} | {'Tamanho':<10} | {'Thumb'}")
            print("-" * 80)
            
            for line in text.split("\n"):
                if not line: continue
                parts = line.split("|")
                filename = parts[0]
                autor = parts[1]
                date_time = parts[2]
                tamanho = parts[3]
                has_thumb = "Sim" if parts[4] == "1" else "Não"    
                print(f"{filename:<20} | {autor:<10} | {date_time:<20} | {tamanho:<10} | {has_thumb}")

def cmd_download_view(sock, server_addr, mode="DOWNLOAD"):
    nome = input("Nome do arquivo: ").strip()
    cmd = f"{mode}|{nome}"
    
    # envia pedido
    if not rdt_send(sock, cmd, server_addr):
        print("Erro: Falha ao enviar comando.")
        return

    # recebe reposta
    resp = rdt_recv(sock)
    
    if resp:
        resp_str = resp.decode()
        if resp_str.startswith("FOUND"):
            # confirma que ta pronto pra receber dados
            rdt_send(sock, "READY", server_addr)
            
            # recebe arquivo
            file_data = rdt_recv(sock)
            
            if file_data:
                
                # garante que a pasta existe
                os.makedirs(DOWNLOAD_DIR, exist_ok=True)
                
                # define o prefixo
                prefix = "" if mode == "DOWNLOAD" else "thumb_"
                
                #cria o caminho
                caminho_completo = os.path.join(DOWNLOAD_DIR, prefix + nome)
                
                with open(caminho_completo, "wb") as f:
                    f.write(file_data)
                    
                print(f"Sucesso! Arquivo salvo em: {caminho_completo}")

            else:
                print("Erro: Recebimento de dados falhou.")
        else:
            print(f"Erro do servidor: {resp_str}")
    else:
        print("Erro: Servidor não respondeu ao pedido.")

def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_addr = (HOST, PORT)
    
    username = input("Seu usuário: ").strip() or "anon"
    
    while True:
        print("\n1-Upload 2-List 3-Download 4-View 5-Sair")
        op = input("Op: ")
        
        if op == "1": cmd_upload(sock, server_addr, username)
        elif op == "2": cmd_list(sock, server_addr)
        elif op == "3": cmd_download_view(sock, server_addr, "DOWNLOAD")
        elif op == "4": cmd_download_view(sock, server_addr, "VIEW")
        elif op == "5": break

if __name__ == "__main__":
    main()
