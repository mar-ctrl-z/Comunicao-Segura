import requests
import sys

BASE_URL = 'http://127.0.0.1:5000'

token_sessao  = None
usuario_atual = None
papel_atual   = None


# -------------------------------------------------------------------
# Utilitários
# -------------------------------------------------------------------

def cabecalho():
    return {
        'Authorization': f'Bearer {token_sessao}',
        'Content-Type':  'application/json',
    }


def _req(method, rota, **kwargs):
    """Wrapper que trata erros de conexão de forma uniforme."""
    try:
        resp = getattr(requests, method)(f'{BASE_URL}{rota}', **kwargs)
        return resp
    except requests.ConnectionError:
        print('\n[ERRO] Não foi possível conectar ao servidor.')
        print('       Verifique se server.py está em execução e se BASE_URL está correto.')
        return None


def separador(titulo=''):
    largura = 50
    if titulo:
        print(f'\n{"─"*3} {titulo} {"─"*(largura - len(titulo) - 5)}')
    else:
        print('─' * largura)


# -------------------------------------------------------------------
# Ações do menu
# -------------------------------------------------------------------

def fazer_login():
    global token_sessao, usuario_atual, papel_atual
    separador('LOGIN')
    username = input('Username : ').strip()
    senha    = input('Senha    : ').strip()

    resp = _req('post', '/login', json={'username': username, 'senha': senha})
    if resp is None:
        return

    dados = resp.json()
    if resp.status_code == 200:
        token_sessao  = dados['token']
        usuario_atual = username
        papel_atual   = dados['papel']
        print(f'\n  {dados["mensagem"]}')
        print(f'  Papel   : {papel_atual}')
        print(f'  Token   : {token_sessao[:24]}...  (expira em {dados["expira_em_min"]} min)')
    else:
        print(f'\n  [NEGADO] {dados.get("erro")}')


def fazer_logout():
    global token_sessao, usuario_atual, papel_atual
    if not token_sessao:
        print('  Você não está logado.')
        return

    _req('post', '/logout', headers=cabecalho())
    print(f'\n  Sessão de "{usuario_atual}" encerrada.')
    token_sessao  = None
    usuario_atual = None
    papel_atual   = None


def enviar_mensagem():
    if not token_sessao:
        print('\n  Faça login primeiro.')
        return

    separador('ENVIAR MENSAGEM')
    destinatario = input('Destinatário : ').strip()
    conteudo     = input('Mensagem     : ').strip()

    resp = _req(
        'post', '/mensagem/enviar',
        headers=cabecalho(),
        json={'destinatario': destinatario, 'conteudo': conteudo}
    )
    if resp is None:
        return

    dados = resp.json()
    if resp.status_code == 200:
        print(f'\n  Enviado em {dados["timestamp"]}')
        print(f'  Tamanho cifrado no servidor: {dados["bytes_cifrados"]} bytes')
    else:
        print(f'\n  [ERRO] {dados.get("erro")}')


def ler_caixa_de_entrada():
    if not token_sessao:
        print('\n  Faça login primeiro.')
        return

    resp = _req('get', '/mensagem/caixa-de-entrada', headers=cabecalho())
    if resp is None:
        return

    dados = resp.json()
    if resp.status_code != 200:
        print(f'\n  [ERRO] {dados.get("erro")}')
        return

    mensagens = dados['mensagens']
    separador(f'CAIXA DE ENTRADA — {usuario_atual} ({dados["total"]} mensagem(ns))')

    if not mensagens:
        print('  Nenhuma mensagem.')
        return

    for m in mensagens:
        icone = '[ nova ]' if m['lida'] == 0 else '[  lida ]'
        print(f'\n  {icone}  De: {m["remetente"]}  |  {m["timestamp"]}')
        print(f'           {m["conteudo"]}')


def ver_enviadas():
    if not token_sessao:
        print('\n  Faça login primeiro.')
        return

    resp = _req('get', '/mensagem/enviadas', headers=cabecalho())
    if resp is None:
        return

    dados = resp.json()
    if resp.status_code != 200:
        print(f'\n  [ERRO] {dados.get("erro")}')
        return

    enviadas = dados['enviadas']
    separador(f'MENSAGENS ENVIADAS — {usuario_atual} ({dados["total"]})')

    if not enviadas:
        print('  Nenhuma mensagem enviada.')
        return

    for m in enviadas:
        lida = 'lida' if m['lida'] else 'não lida'
        print(f'  #{m["id"]:03d}  Para: {m["destinatario"]:12}  {m["timestamp"]}  [{lida}]')


def ler_todas_mensagens():
    if not token_sessao:
        print('\n  Faça login primeiro.')
        return

    resp = _req('get', '/mensagem/todas', headers=cabecalho())
    if resp is None:
        return

    dados = resp.json()
    if resp.status_code != 200:
        print(f'\n  [ACESSO NEGADO] {dados.get("erro")}')
        return

    mensagens = dados['mensagens']
    separador(f'TODAS AS MENSAGENS [ADMIN] — {dados["total"]} no total')

    for m in mensagens:
        lida = 'lida' if m['lida'] else 'não lida'
        print(f'\n  #{m["id"]:03d}  {m["remetente"]} -> {m["destinatario"]}  |  {m["timestamp"]}  [{lida}]')
        print(f'       {m["conteudo"]}')


def cadastrar_usuario():
    if not token_sessao:
        print('\n  Faça login primeiro.')
        return

    separador('CADASTRAR USUÁRIO [ADMIN]')
    novo_usr = input('Novo username     : ').strip()
    senha    = input('Senha             : ').strip()
    papel    = input('Papel (user/admin): ').strip() or 'user'

    resp = _req(
        'post', '/usuario/cadastrar',
        headers=cabecalho(),
        json={'username': novo_usr, 'senha': senha, 'papel': papel}
    )
    if resp is None:
        return

    dados = resp.json()
    if resp.status_code == 200:
        print(f'\n  {dados["mensagem"]}')
    else:
        print(f'\n  [ERRO] {dados.get("erro")}')


def listar_usuarios():
    if not token_sessao:
        print('\n  Faça login primeiro.')
        return

    resp = _req('get', '/usuario/listar', headers=cabecalho())
    if resp is None:
        return

    dados = resp.json()
    if resp.status_code != 200:
        print(f'\n  [ACESSO NEGADO] {dados.get("erro")}')
        return

    separador(f'USUÁRIOS CADASTRADOS  (sessões abertas: {dados["sessoes_abertas"]})')
    print(f'  {"USERNAME":<15} {"PAPEL":<8} STATUS')
    print(f'  {"-"*14} {"-"*7} ------')
    for u in dados['usuarios']:
        status = '● online' if u['sessao_ativa'] else '  offline'
        print(f'  {u["username"]:<15} {u["papel"]:<8} {status}')


# -------------------------------------------------------------------
# Menu principal
# -------------------------------------------------------------------

OPCOES_BASE = {
    '1': ('Login',                    fazer_login),
    '2': ('Logout',                   fazer_logout),
    '3': ('Enviar mensagem',          enviar_mensagem),
    '4': ('Caixa de entrada',         ler_caixa_de_entrada),
    '5': ('Mensagens enviadas',       ver_enviadas),
    '0': ('Sair',                     None),
}

OPCOES_ADMIN = {
    '6': ('Ver todas as mensagens  [admin]', ler_todas_mensagens),
    '7': ('Cadastrar usuário       [admin]', cadastrar_usuario),
    '8': ('Listar usuários         [admin]', listar_usuarios),
}


def menu():
    while True:
        print('\n' + '═' * 50)
        print('  SISTEMA DE COMUNICAÇÃO SEGURA')
        if usuario_atual:
            print(f'  Sessão: {usuario_atual}  |  papel: {papel_atual}')
        else:
            print('  Sessão: não autenticado')
        print('═' * 50)

        opcoes = dict(OPCOES_BASE)
        if papel_atual == 'admin':
            opcoes.update(OPCOES_ADMIN)

        for k, (descricao, _) in sorted(opcoes.items()):
            print(f'  [{k}] {descricao}')

        escolha = input('\n  Escolha: ').strip()

        if escolha == '0':
            if token_sessao:
                fazer_logout()
            print('\n  Até logo.\n')
            sys.exit(0)

        if escolha in opcoes:
            opcoes[escolha][1]()
        else:
            print('  Opção inválida.')


if __name__ == '__main__':
    print()
    print('  ╔══════════════════════════════════════════════╗')
    print('  ║     CLIENTE — COMUNICAÇÃO SEGURA  v1.0       ║')
    print('  ║     Conectado em:', BASE_URL.ljust(27), '║')
    print('  ╚══════════════════════════════════════════════╝')
    menu()
