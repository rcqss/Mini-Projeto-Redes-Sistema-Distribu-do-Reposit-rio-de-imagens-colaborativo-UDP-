Mini-Projeto-Redes-Sistema-Distribu-do-Reposit-rio-de-imagens-colaborativo
atividade proposta na cadeira de Introdução aos Sistemas Distribuídos e Redes do CIn UFPE


💡 Objetivo Central
O objetivo deste projeto é implementar um sistema de repositório colaborativo de imagens utilizando o protocolo UDP (User Datagram Protocol), focado em construir a confiabilidade da comunicação sobre um protocolo inerentemente não confiável.

A arquitetura é Cliente-Servidor, onde o mecanismo de Transferência de Dados Confiável (RDT - Stop-and-Wait) é implementado sobre os sockets UDP para garantir a entrega correta de comandos e arquivos.

📝 Funcionalidades
O sistema implementa os seguintes comandos, garantindo a entrega confiável de dados via RDT:

Upload de imagens: Envio de arquivos do cliente para o servidor, com registro de autor e criação de metadados.

Listagem de imagens: O servidor envia de forma confiável a lista de metadados das imagens disponíveis (nome, autor, tamanho, data).

Download de imagens: Transferência confiável do arquivo original do servidor para o cliente.

Visualização de miniaturas (Thumbnails): Transferência confiável de uma versão reduzida da imagem (thumbnail) para visualização rápida.

🛠️ Tecnologias e Protocolos
Linguagem: Python

Comunicação: Sockets UDP (socket.socket(socket.AF_INET, socket.SOCK_DGRAM))

Protocolo de Confiança: RDT (Reliable Data Transfer) do tipo Stop-and-Wait, implementado nas funções rdt_send e rdt_recv para controle de fluxo e retransmissão via timeout.

Empacotamento de Dados: Módulo struct para manipular o cabeçalho binário dos pacotes (número de sequência e tamanho).

Manipulação de Imagens: Biblioteca Pillow (PIL) para gerar as miniaturas (thumbnails).

📂 Estrutura do Projeto
.
├── server.py   # Servidor UDP: implementa RDT, processa comandos (UPLOAD, LIST, DOWNLOAD, VIEW) e gerencia metadados.
├── client.py   # Cliente UDP: implementa RDT, menu interativo, envia comandos e recebe/salva arquivos.
├── metadata.json # Arquivo gerado para armazenar o catálogo de imagens.
└── README.md   # Este arquivo
▶️ Como Rodar o Projeto
Pré-requisitos:
Python 3 instalado

pip funcionando

A biblioteca Pillow instalada:

Bash

pip install Pillow
Rodando o Servidor
Abra um terminal na pasta raiz do projeto.

Execute o servidor:

Bash

python server.py
O servidor iniciará a escuta em 0.0.0.0:5000 (ou a porta configurada).

Mantenha este terminal aberto. Ele mostrará logs das transferências e comandos RDT.

Rodando o Cliente
Abra outro terminal na mesma pasta do projeto.

Execute o cliente:

Bash

python client.py
O cliente pedirá o nome de usuário e exibirá o menu de comandos.

🧠 Foco da Implementação (RDT)
A lógica central do projeto reside em:

rdt_send: Quebra o arquivo/comando em chunks, anexa o número de sequência, envia e entra em timeout esperando o ACK correspondente. Se o ACK não chegar, o pacote é retransmitido.

rdt_recv: Recebe os pacotes, verifica o número de sequência (expected_seq), envia o ACK para o pacote correto e descarta ou trata pacotes duplicados/fora de ordem.

Handshake de Tamanho: Um passo inicial onde o remetente avisa o tamanho total esperado, crucial para que o receptor saiba quando a transferência terminou.
