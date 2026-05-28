import socket
import threading
import sqlite3
import hashlib
import uuid
import json
import base64
from datetime import datetime
from cryptography.fernet import Fernet

# Configurações de Rede (Escuta em todas as interfaces para permitir múltiplos PCs)
HOST = '0.0.0.0'
PORT = 5555

# Chave Simétrica Compartilhada (Gerada a partir de 32 bytes estáticos para simplificação)
SHARED_KEY = base64.urlsafe_b64encode(b"chave_secreta_com_32_bytes_comp!")
fernet = Fernet(SHARED_KEY)

# Dicionário em memória para gerenciar sessões ativas {token: {"username": ..., "role": ...}}
active_sessions = {}

def init_db():
    """Inicializa o banco de dados e cria usuários padrão caso não existam."""
    conn = sqlite3.connect('sistema_seguro.db')
    cursor = conn.cursor()
    
    # Tabela de Usuários
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            username TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL
        )
    ''')
    
    # Tabela de Mensagens conforme especificação
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS mensagens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            remetente TEXT NOT NULL,
            destinatario TEXT NOT NULL,
            conteudo_cifrado BLOB NOT NULL,
            timestamp TEXT NOT NULL,
            lida INTEGER NOT NULL
        )
    ''')
    
    # Inserção de usuários de teste (Senhas: admin123, userA123, userB123)
    users_to_create = [
        ('admin', hashlib.sha256(b'admin123').hexdigest(), 'admin'),
        ('userA', hashlib.sha256(b'userA123').hexdigest(), 'user'),
        ('userB', hashlib.sha256(b'userB123').hexdigest(), 'user')
    ]
    
    for username, p_hash, role in users_to_create:
        try:
            cursor.execute('INSERT INTO usuarios VALUES (?, ?, ?)', (username, p_hash, role))
        except sqlite3.IntegrityError:
            pass # Usuário já existe
            
    conn.commit()
    conn.close()

def handle_client(client_socket):
    """Gerencia a comunicação individual com cada cliente via protocolo JSON."""
    buffer = ""
    try:
        while True:
            data = client_socket.recv(4096).decode('utf-8')
            if not data:
                break
                
            buffer += data
            while '\n' in buffer:
                line, buffer = buffer.split('\n', 1)
                if not line.strip():
                    continue
                
                request = json.loads(line)
                response = process_request(request)
                client_socket.sendall((json.dumps(response) + '\n').encode('utf-8'))
    except Exception as e:
        print(f"[-] Erro na conexão: {e}")
    finally:
        client_socket.close()

def process_request(req):
    action = req.get("action")
    token = req.get("token")
    
    # 1. Fluxo de Autenticação (Não exige Token)
    if action == "login":
        username = req.get("username")
        password = req.get("password")
        p_hash = hashlib.sha256(password.encode()).hexdigest()
        
        conn = sqlite3.connect('sistema_seguro.db')
        cursor = conn.cursor()
        cursor.execute('SELECT role FROM usuarios WHERE username=? AND password_hash=?', (username, p_hash))
        user = cursor.fetchone()
        conn.close()
        
        if user:
            session_token = str(uuid.uuid4())
            active_sessions[session_token] = {"username": username, "role": user[0]}
            return {"status": "success", "token": session_token, "role": user[0], "username": username}
        return {"status": "error", "message": "Credenciais inválidas. Acesso negado."}

    # Validação do Token para as demais ações
    if not token or token not in active_sessions:
        return {"status": "error", "message": "Não autenticado ou token expirado."}
        
    session = active_sessions[token]
    current_user = session["username"]
    current_role = session["role"]

    conn = sqlite3.connect('sistema_seguro.db')
    cursor = conn.cursor()

    # 2. Enviar Mensagem (User e Admin podem enviar para qualquer um)
    if action == "send_msg":
        dest = req.get("destinatario")
        conteudo_cifrado_str = req.get("conteudo_cifrado") # String Base64 vinda do cliente
        
        # Verificar se destinatário existe
        cursor.execute('SELECT 1 FROM usuarios WHERE username=?', (dest,))
        if not cursor.fetchone():
            conn.close()
            return {"status": "error", "message": "Destinatário não encontrado."}
            
        timestamp = datetime.now().isoformat()
        cursor.execute('''
            INSERT INTO mensagens (remetente, destinatario, conteudo_cifrado, timestamp, lida)
            VALUES (?, ?, ?, ?, 0)
        ''', (current_user, dest, conteudo_cifrado_str.encode('utf-8'), timestamp))
        conn.commit()
        conn.close()
        return {"status": "success", "message": "Mensagem enviada com sucesso."}

    # 3. Ler Próprias Mensagens (User e Admin)
    elif action == "read_msgs":
        cursor.execute('SELECT id, remetente, destinatario, conteudo_cifrado, timestamp FROM mensagens WHERE destinatario=?', (current_user,))
        rows = cursor.fetchall()
        
        msgs = []
        for r_id, rem, dest, cifrado, ts in rows:
            # O servidor descriptografa apenas no momento da entrega
            decrito = fernet.decrypt(cifrado).decode('utf-8')
            msgs.append({"id": r_id, "remetente": rem, "destinatario": dest, "conteudo": decrito, "timestamp": ts})
            cursor.execute('UPDATE mensagens SET lida=1 WHERE id=?', (r_id,))
            
        conn.commit()
        conn.close()
        return {"status": "success", "messages": msgs}

    # 4. Ler Mensagens de Outros (Apenas Admin)
    elif action == "read_all_msgs":
        if current_role != "admin":
            conn.close()
            return {"status": "error", "message": "Acesso negado: Requer papel de admin."}
            
        cursor.execute('SELECT id, remetente, destinatario, conteudo_cifrado, timestamp FROM mensagens')
        rows = cursor.fetchall()
        
        msgs = []
        for r_id, rem, dest, cifrado, ts in rows:
            decrito = fernet.decrypt(cifrado).decode('utf-8')
            msgs.append({"id": r_id, "remetente": rem, "destinatario": dest, "conteudo": decrito, "timestamp": ts})
            
        conn.close()
        return {"status": "success", "messages": msgs}

    # 5. Cadastrar Novo Usuário (Apenas Admin)
    elif action == "register_user":
        if current_role != "admin":
            conn.close()
            return {"status": "error", "message": "Acesso negado: Requer papel de admin."}
            
        new_user = req.get("new_username")
        new_pass = req.get("new_password")
        new_role = req.get("new_role", "user")
        
        new_hash = hashlib.sha256(new_pass.encode()).hexdigest()
        try:
            cursor.execute('INSERT INTO usuarios VALUES (?, ?, ?)', (new_user, new_hash, new_role))
            conn.commit()
            res = {"status": "success", "message": f"Usuário {new_user} cadastrado."}
        except sqlite3.IntegrityError:
            res = {"status": "error", "message": "Usuário já existe."}
        conn.close()
        return res

    # 6. Ver lista de usuários ativos (Apenas Admin)
    elif action == "list_active":
        if current_role != "admin":
            conn.close()
            return {"status": "error", "message": "Acesso negado: Requer papel de admin."}
        
        conn.close()
        actives = [sess["username"] for sess in active_sessions.values()]
        return {"status": "success", "active_users": list(set(actives))}

    conn.close()
    return {"status": "error", "message": "Ação desconhecida."}

def main():
    init_db()
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((HOST, PORT))
    server.listen(5)
    print(f"[*] Servidor de Comunicação Segura rodando na porta {PORT}...")
    print("[*] Aguardando conexões de rede local...")
    
    try:
        while True:
            client_sock, addr = server.accept()
            print(f"[+] Conexão aceita de {addr[0]}:{addr[1]}")
            threading.Thread(target=handle_client, args=(client_sock,), daemon=True).start()
    except KeyboardInterrupt:
        print("\n[-] Desligando o servidor.")
    finally:
        server.close()

if __name__ == "__main__":
    main()