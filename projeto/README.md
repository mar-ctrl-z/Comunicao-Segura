# Sistema de Comunicação Segura entre Processos Distribuídos

Sistema distribuído de troca de mensagens com autenticação, criptografia simétrica e controle de acesso baseado em papéis (RBAC).

---

## Arquitetura de Segurança

| Camada | Mecanismo | Tecnologia |
|---|---|---|
| Autenticação | Hash SHA-256 das senhas + token de sessão aleatório | `hashlib`, `secrets` |
| Criptografia | Fernet (AES-128-CBC + HMAC-SHA256) | `cryptography` |
| Controle de acesso | Papéis `user` e `admin` verificados em cada endpoint | Flask + SQLite |
| Persistência | Mensagens gravadas cifradas no banco | SQLite |

### Fluxo de segurança

```
Cliente                        Servidor
  |                               |
  |-- POST /login (usr+senha) --> |
  |                               |-- verifica SHA-256 hash
  |<-- token de sessão -----------|
  |                               |
  |-- POST /mensagem/enviar ----> |  (header: Authorization: Bearer <token>)
  |   conteudo em texto plano     |-- cifra com Fernet
  |                               |-- grava conteudo_cifrado no SQLite
  |                               |
  |-- GET /mensagem/caixa ------> |-- descriptografa na entrega
  |<-- mensagens em texto claro --|
```

---

## Instalação

```bash
# Clone o repositório
git clone <url-do-repositorio>
cd <pasta>

# Crie um ambiente virtual (recomendado)
python -m venv venv
source venv/bin/activate   # Linux/macOS
venv\Scripts\activate      # Windows

# Instale as dependências
pip install -r requirements.txt
```

---

## Como Executar

### 1. Iniciar o servidor (Notebook A)

```bash
cd server
python server.py
```

O servidor inicia em `http://0.0.0.0:5000` e cria automaticamente o banco `mensagens.db` com três usuários padrão:

| Username | Senha     | Papel |
|----------|-----------|-------|
| admin    | admin123  | admin |
| alice    | alice123  | user  |
| bob      | bob123    | user  |

### 2. Iniciar o cliente (Notebook B ou C)

> Edite `BASE_URL` em `client/client.py` para apontar ao IP do servidor se estiver em máquinas diferentes.

```bash
cd client
python client.py
```

---

## Fluxo de Demonstração

1. **Servidor rodando** — mensagem de inicialização aparece no terminal.
2. **Login com senha errada** — opção 1, credenciais inválidas → `✘ Credenciais inválidas`.
3. **Login válido (alice)** — token de sessão exibido.
4. **Envio de mensagem** — alice envia para bob; mensagem trafega cifrada.
5. **Leitura (bob)** — faz login como bob, opção 4 mostra mensagens descriptografadas.
6. **Controle de acesso** — usuário comum tenta opção 5 (todas as mensagens) → `✘ Acesso negado`.
7. **Login como admin** — visualiza todas as mensagens e lista de usuários.
8. **Verificação no banco** — `sqlite3 server/mensagens.db "SELECT conteudo_cifrado FROM mensagens;"` mostra bytes cifrados.

---

## Estrutura do Projeto

```
├── server/
│   └── server.py        # API Flask: autenticação, criptografia, controle de acesso
├── client/
│   └── client.py        # Cliente interativo de linha de comando
├── requirements.txt
└── README.md
```

---

## Endpoints da API

| Método | Rota | Papel mínimo | Descrição |
|--------|------|--------------|-----------|
| POST | `/login` | — | Autenticar e obter token |
| POST | `/logout` | user | Encerrar sessão |
| POST | `/mensagem/enviar` | user | Enviar mensagem cifrada |
| GET  | `/mensagem/caixa-de-entrada` | user | Ler próprias mensagens |
| GET  | `/mensagem/todas` | admin | Ver todas as mensagens |
| POST | `/usuario/cadastrar` | admin | Cadastrar novo usuário |
| GET  | `/usuario/listar` | admin | Listar usuários e sessões ativas |
