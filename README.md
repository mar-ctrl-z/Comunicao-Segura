# Sistema de Comunicação Segura entre Processos Distribuídos

Este projeto consiste em um sistema distribuído simplificado para a troca de mensagens seguras entre processos utilizando **Python Sockets TCP** nativos, aplicando mecanismos fundamentais de segurança da informação: autenticação baseada em posse de token, criptografia simétrica de ponta a ponta e controle de acesso baseado em papéis (RBAC).

O sistema foi desenhado para operar em ambiente de rede local (LAN), permitindo que computadores fisicamente distintos (Notebook A, Notebook B, etc.) se comuniquem com segurança.

---

## 🛡️ Arquitetura de Segurança Implementada

A arquitetura do sistema garante o cumprimento de três pilares fundamentais da segurança:

1. **Autenticação (Quem é você?):** Nenhuma requisição de envio ou leitura é processada sem que o usuário esteja autenticado. As senhas **nunca** transitam ou são armazenadas em texto claro; em vez disso, utiliza-se a função hash criptográfica **SHA-256** (via biblioteca `hashlib`). Ao efetuar o login, o servidor gera um token de sessão dinâmico e seguro via `uuid`, exigido no cabeçalho de todas as mensagens seguintes.
2. **Criptografia (Confidencialidade):** As mensagens são cifradas localmente no cliente antes de trafegarem pela rede utilizando criptografia simétrica através da biblioteca `cryptography` (módulo **Fernet**). O servidor armazena os dados cifrados e só realiza a descriptografia no momento exato da entrega ao destinatário legítimo.
3. **Controle de Acesso (O que você pode fazer?):** Implementação de uma matriz de controle de acesso baseada em papéis (`user` e `admin`):
   * **Usuário Comum (`user`):** Pode enviar mensagens para qualquer usuário e ler exclusivamente as mensagens destinadas a si mesmo.
   * **Administrador (`admin`):** Possui privilégios elevados para auditar e ler todas as mensagens do sistema, cadastrar novos usuários através de endpoint exclusivo e monitorar quem está ativo no momento.

---

## 📂 Organização do Repositório

O projeto está estruturado da seguinte forma:

```text
├── requirements.txt      # Dependências do projeto
├── README.md             # Documentação oficial e guia de execução
├── server/               # Diretório do processo Servidor
│   └── server.py         # Código-fonte do servidor    central e gerenciador do banco
└── client/               # Diretório do processo Cliente
    └── client.py         # Interface e lógica de criptografia do cliente
```

---

## 🚀 Instruções de Instalação e Configuração

### 1. Pré-requisitos

Certifique-se de ter o Python 3.11+ instalado em todas as máquinas envolvidas.

### 2. Criar e Ativar a Venv

```bash 
## Windows
python -m venv venv
venv\Scripts\activate

## Linux/MacOS
python3 -m venv venv
source venv\bin\activate
```

### 3. Instalação das Dependências

Em todos os computadores que executarão o sistema, instale a biblioteca necessária através do terminal:

```bash
pip install -r requirements.txt
```

---

## 💻 Configuração de Rede e Execução

Para permitir a comunicação entre computadores diferentes, o servidor foi configurado para escutar no endereço 0.0.0.0 (todas as interfaces de rede disponíveis).

### Passo 1: Descobrir o IP do Servidor (Notebook A)

No computador que agirá como servidor central, abra o terminal e descubra o IP local da máquina:

* **No Windows**: ipconfig (procure pelo Endereço IPv4, ex: 192.168.1.50).

* **No Linux/Mac**: hostname -I ou ifconfig.

### Passo 2: Iniciar o Servidor (Notebook A)

Navegue até a pasta do servidor:

```bash
cd server
```

e execute:

```bash
## No Windows
python server.py

## No Linux/MacOS
python3 server.py
```

O servidor inicializará o banco de dados SQLite (sistema_seguro.db) e criará automaticamente 3 usuários padrão para testes: 

| Usuário | Senha | Descrição |
| -------- | ----- | ----------- |
| admin | admin123 | Papel: admin |
| userA | userA123 | Papel: user |
| userB | userB123 | Papel: user |

### Passo 3: Iniciar os Clientes (Notebook B / C)

Nos computadores clientes, acesse:

```bash
cd client
```

e execute:

```bash
## No Windows
python client.py

## No Linux\MacOS

python3 client.py
```

Ao iniciar, o programa solicitará o IP do Servidor. Insira o IP anotado no Passo 1.

---