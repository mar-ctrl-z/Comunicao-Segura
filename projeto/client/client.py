import socket
import json
import base64
from cryptography.fernet import Fernet

# Chave Simétrica de Criptografia idêntica à do servidor
SHARED_KEY = base64.urlsafe_b64encode(b"chave_secreta_com_32_bytes_comp!")
fernet = Fernet(SHARED_KEY)

PORT = 5555

class SecureClient:
    def __init__(self, server_ip, server_port):
        self.server_ip = server_ip
        self.server_port = server_port
        self.token = None
        self.username = None
        self.role = None
        self.sock = None
        self.reader = None

    def connect(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.server_ip, self.server_port))
        # Utiliza makefile para ler facilmente linhas terminadas em '\n'
        self.reader = self.sock.makefile('r', encoding='utf-8')

    def send_request(self, req):
        if self.token:
            req["token"] = self.token
        
        payload = json.dumps(req) + '\n'
        self.sock.sendall(payload.encode('utf-8'))
        
        response_line = self.reader.readline()
        if not response_line:
            return {"status": "error", "message": "Conexão perdida com o servidor."}
        return json.loads(response_line)

    def login(self, username, password):
        req = {"action": "login", "username": username, "password": password}
        res = self.send_request(req)
        if res.get("status") == "success":
            self.token = res.get("token")
            self.username = res.get("username")
            self.role = res.get("role")
        return res

    def send_message(self, dest, msg_text):
        # Criptografa a mensagem localmente antes do envio de rede
        cipher_bytes = fernet.encrypt(msg_text.encode('utf-8'))
        cipher_str = cipher_bytes.decode('utf-8') # Converte para string para transitar no JSON
        
        req = {"action": "send_msg", "destinatario": dest, "conteudo_cifrado": cipher_str}
        return self.send_request(req)

    def read_my_messages(self):
        req = {"action": "read_msgs"}
        return self.send_request(req)

    def admin_read_all(self):
        req = {"action": "read_all_msgs"}
        return self.send_request(req)

    def admin_register_user(self, new_user, new_pass, new_role):
        req = {"action": "register_user", "new_username": new_user, "new_password": new_pass, "new_role": new_role}
        return self.send_request(req)

    def admin_list_active(self):
        req = {"action": "list_active"}
        return self.send_request(req)

    def close(self):
        if self.sock:
            self.sock.close()

def menu_principal(client):
    while True:
        print(f"\n--- Menu ({client.username} | Papel: {client.role}) ---")
        print("1. Enviar Mensagem")
        print("2. Ler Minhas Mensagens")
        
        if client.role == "admin":
            print("[ADMIN] 3. Ler TODAS as Mensagens do Sistema")
            print("[ADMIN] 4. Cadastrar Novo Usuário")
            print("[ADMIN] 5. Listar Usuários Ativos")
            
        print("6. Sair")
        opcao = input("Escolha uma opção: ")

        if opcao == "1":
            dest = input("Destinatário: ")
            msg = input("Mensagem: ")
            res = client.send_message(dest, msg)
            print(f"Resposta: {res.get('message', res.get('error'))}")
            
        elif opcao == "2":
            res = client.read_my_messages()
            if res.get("status") == "success":
                print("\n=== Minhas Mensagens ===")
                for m in res.get("messages", []):
                    print(f"[{m['timestamp']}] De: {m['remetente']} -> Msg: {m['conteudo']}")
            else:
                print(f"Erro: {res.get('message')}")
                
        elif opcao == "3" and client.role == "admin":
            res = client.admin_read_all()
            if res.get("status") == "success":
                print("\n=== Auditoria: Todas as Mensagens ===")
                for m in res.get("messages", []):
                    print(f"[{m['timestamp']}] {m['remetente']} para {m['destinatario']}: {m['conteudo']}")
            else:
                print(f"Erro: {res.get('message')}")
                
        elif opcao == "4" and client.role == "admin":
            n_user = input("Novo Username: ")
            n_pass = input("Nova Senha: ")
            n_role = input("Papel (user/admin): ")
            res = client.admin_register_user(n_user, n_pass, n_role)
            print(f"Resposta: {res.get('message')}")
            
        elif opcao == "5" and client.role == "admin":
            res = client.admin_list_active()
            print(f"Usuários ativos em sessão: {res.get('active_users')}")
            
        elif opcao == "6":
            break
        else:
            print("Opção inválida ou não autorizada.")

def main():
    print("=== Cliente de Mensataria Segura Distribuída ===")
    ip = input("Digite o IP do Servidor (ex: 192.168.1.50): ")
    
    client = SecureClient(ip, PORT)
    try:
        client.connect()
    except Exception as e:
        print(f"Não foi possível conectar ao servidor {ip}:{PORT}. Erro: {e}")
        return

    # Loop de autenticação obrigatório
    while True:
        print("\n--- Tela de Login ---")
        user = input("Usuário: ")
        senha = input("Senha: ")
        
        res = client.login(user, senha)
        if res.get("status") == "success":
            print(f"\n[+] Login efetuado com sucesso! Token gerado.")
            break
        else:
            print(f"[-] Erro: {res.get('message')}")
            cont = input("Tentar novamente? (s/n): ")
            if cont.lower() != 's':
                client.close()
                return

    try:
        menu_principal(client)
    finally:
        client.close()

if __name__ == "__main__":
    main()