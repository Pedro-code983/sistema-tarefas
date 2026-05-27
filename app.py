from flask import Flask, render_template, request, redirect, flash, session
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "roysse_secret_key"
DB_NAME = "database.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # 1. Tabela de Usuários
    c.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)
    
    # 2. Tabela de Tarefas (com usuario_id para isolamento de dados)
    c.execute("""
        CREATE TABLE IF NOT EXISTS tarefas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER,
            titulo TEXT NOT NULL,
            descricao TEXT,
            status TEXT DEFAULT 'pendente',
            data_limite TEXT,
            prioridade TEXT DEFAULT 'Média',
            categoria TEXT DEFAULT 'Geral'
        )
    """)
    
    # 3. Tabela de Perfil / Cookies vinculada por Usuário
    c.execute("""
        CREATE TABLE IF NOT EXISTS perfil (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER UNIQUE,
            cookies INTEGER DEFAULT 0
        )
    """)
    
    # 4. Tabela da Loja Geral
    c.execute("""
        CREATE TABLE IF NOT EXISTS loja (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            preco INTEGER NOT NULL,
            descricao TEXT
        )
    """)
    
    # 5. Tabela de Inventário (Itens Comprados por cada usuário)
    c.execute("""
        CREATE TABLE IF NOT EXISTS inventario (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER,
            nome TEXT NOT NULL,
            descricao TEXT
        )
    """)

    # 6. Tabela de Logs e Auditoria
    c.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER,
            mensagem TEXT NOT NULL,
            data_hora TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # OTIMIZAÇÃO DE PERFORMANCE: Criação de Índices Estratégicos para consultas ultra rápidas
    c.execute("CREATE INDEX IF NOT EXISTS idx_tarefas_usuario ON tarefas(usuario_id)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_tarefas_categoria ON tarefas(categoria)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_tarefas_status ON tarefas(status)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_logs_usuario_data ON logs(usuario_id, data_hora DESC)")

    # Popula a loja padrão se estiver vazia
    c.execute("SELECT COUNT(*) FROM loja")
    if c.fetchone()[0] == 0:
        mimos = [
            ('2h de Videogame', 50, 'Liberado jogar sem culpa'),
            ('Ver 2 eps de Série', 30, 'Netflix / HBO / Disney+'),
            ('Pedir um Lanche', 100, 'Aquele iFood merecido')
        ]
        c.executemany("INSERT INTO loja (nome, preco, descricao) VALUES (?, ?, ?)", mimos)
        
    conn.commit()
    conn.close()

init_db()

# --- FUNÇÃO AUXILIAR DE LOGS ---
def salvar_log(usuario_id, mensagem):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO logs (usuario_id, mensagem) VALUES (?, ?)", (usuario_id, mensagem))
    conn.commit()
    conn.close()

# --- ROTAS DE AUTENTICAÇÃO (SESSÃO E MIDDLEWARE) ---
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username").strip()
        password = request.form.get("password")
        
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("SELECT id, password FROM usuarios WHERE username = ?", (username,))
        user = c.fetchone()
        conn.close()
        
        if user and check_password_hash(user[1], password):
            session["user_id"] = user[0]
            session["username"] = username
            salvar_log(user[0], f"Usuário '{username}' realizou login no sistema.")
            return redirect("/")
        else:
            flash("Usuário ou senha incorretos!", "error")
            
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username").strip()
        password = request.form.get("password")
        
        if username and password:
            hashed_password = generate_password_hash(password)
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            try:
                c.execute("INSERT INTO usuarios (username, password) VALUES (?, ?)", (username, hashed_password))
                user_id = c.lastrowid
                # Cria automaticamente o perfil de cookies zerado para o novo usuário
                c.execute("INSERT INTO perfil (usuario_id, cookies) VALUES (?, 0)", (user_id,))
                conn.commit()
                salvar_log(user_id, f"Conta criada com sucesso para o usuário '{username}'.")
                flash("Cadastro realizado! Faça o login.", "success")
                return redirect("/login")
            except sqlite3.IntegrityError:
                flash("Este nome de usuário já existe!", "error")
            finally:
                conn.close()
    return render_template("register.html")

@app.route("/logout")
def logout():
    if "user_id" in session:
        salvar_log(session["user_id"], f"Usuário '{session['username']}' deslogou.")
    session.clear()
    return redirect("/login")


# --- ROTAS PRINCIPAIS PROTEGIDAS ---
@app.route("/", methods=["GET", "POST"])
def index():
    if "user_id" not in session:
        return redirect("/login")
        
    user_id = session["user_id"]
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    if request.method == "POST":
        titulo = request.form.get("titulo")
        descricao = request.form.get("descricao")
        data_limite = request.form.get("data_limite")
        prioridade = request.form.get("prioridade")
        categoria = request.form.get("categoria").strip()
        if not categoria:
            categoria = "Geral"
            
        if titulo:
            c.execute("""
                INSERT INTO tarefas (usuario_id, titulo, descricao, data_limite, prioridade, categoria) 
                VALUES (?, ?, ?, ?, ?, ?)
            """, (user_id, titulo, descricao, data_limite, prioridade, categoria))
            conn.commit()
            salvar_log(user_id, f"Nova missão lançada: '{titulo}' na categoria '{categoria}'.")
        return redirect("/")
        
    categoria_selecionada = request.args.get("categoria")

    # Filtra as métricas e contadores apenas para o usuário logado (Performance Otimizada)
    c.execute("SELECT * FROM tarefas WHERE usuario_id = ?", (user_id,))
    todas_tarefas = c.fetchall()
    pendentes = len([t for t in todas_tarefas if t[4] == 'pendente'])
    concluidas = len([t for t in todas_tarefas if t[4] == 'concluida'])

    categorias_existentes = sorted(list(set([t[7] for t in todas_tarefas if t[7]])))

    # Busca as tarefas ativas do usuário aplicando o filtro dinâmico
    if categoria_selecionada:
        c.execute("""
            SELECT id, titulo, descricao, status, data_limite, prioridade, categoria FROM tarefas 
            WHERE usuario_id = ? AND categoria = ? 
            ORDER BY CASE prioridade WHEN 'Alta' THEN 1 WHEN 'Média' THEN 2 ELSE 3 END
        """, (user_id, categoria_selecionada))
    else:
        c.execute("""
            SELECT id, titulo, descricao, status, data_limite, prioridade, categoria FROM tarefas 
            WHERE usuario_id = ? 
            ORDER BY CASE prioridade WHEN 'Alta' THEN 1 WHEN 'Média' THEN 2 ELSE 3 END
        """, (user_id,))
        
    tarefas_exibidas = c.fetchall()

    # Pega o saldo do usuário correspondente
    c.execute("SELECT cookies FROM perfil WHERE usuario_id = ?", (user_id,))
    res_saldo = c.fetchone()
    saldo = res_saldo[0] if res_saldo else 0

    # Busca os últimos 4 logs de auditoria do usuário logado
    c.execute("SELECT mensagem, strftime('%H:%M', data_hora, 'localtime') FROM logs WHERE usuario_id = ? ORDER BY id DESC LIMIT 4", (user_id,))
    logs_recentes = c.fetchall()
    
    conn.close()
    
    return render_template(
        "index.html", 
        tarefas=tarefas_exibidas, 
        pendentes=pendentes, 
        concluidas=concluidas, 
        cookies=saldo,
        categorias=categorias_existentes,
        categoria_ativa=categoria_selecionada,
        logs=logs_recentes,
        username=session["username"]
    )

@app.route("/loja", methods=["GET", "POST"])
def loja():
    if "user_id" not in session:
        return redirect("/login")
        
    user_id = session["user_id"]
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    if request.method == "POST":
        nome = request.form.get("nome")
        preco = request.form.get("preco")
        descricao = request.form.get("descricao")
        if nome and preco:
            c.execute("INSERT INTO loja (nome, preco, descricao) VALUES (?, ?, ?)", (nome, preco, descricao))
            conn.commit()
            salvar_log(user_id, f"Adicionou um novo item personalizado à loja global: '{nome}'.")
        return redirect("/loja")

    c.execute("SELECT * FROM loja")
    itens = c.fetchall()
    
    c.execute("SELECT * FROM inventario WHERE usuario_id = ? ORDER BY id DESC", (user_id,))
    meus_itens = c.fetchall()
    
    c.execute("SELECT cookies FROM perfil WHERE usuario_id = ?", (user_id,))
    res_saldo = c.fetchone()
    saldo = res_saldo[0] if res_saldo else 0
    conn.close()
    return render_template("loja.html", itens=itens, cookies=saldo, meus_itens=meus_itens, username=session["username"])

@app.route("/comprar/<int:item_id>", methods=["POST"])
def comprar(item_id):
    if "user_id" not in session:
        return redirect("/login")
        
    user_id = session["user_id"]
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT preco, nome, descricao FROM loja WHERE id=?", (item_id,))
    res_item = c.fetchone()
    c.execute("SELECT cookies FROM perfil WHERE usuario_id=?", (user_id,))
    res_saldo = c.fetchone()

    if res_item and res_saldo:
        preco, nome, descricao = res_item[0], res_item[1], res_item[2]
        saldo = res_saldo[0]

        if saldo >= preco:
            c.execute("UPDATE perfil SET cookies = cookies - ? WHERE usuario_id=?", (preco, user_id))
            c.execute("INSERT INTO inventario (usuario_id, nome, descricao) VALUES (?, ?, ?)", (user_id, nome, descricao))
            conn.commit()
            salvar_log(user_id, f"Resgatou o mimo '{nome}' gastando {preco} cookies.")
            flash(f"Sucesso! Você resgatou: {nome}", "success")
        else:
            flash(f"Saldo insuficiente para {nome}!", "error")
            
    conn.close()
    return redirect("/loja")

@app.route("/concluir/<int:tarefa_id>", methods=["POST"])
def concluir(tarefa_id):
    if "user_id" not in session:
        return redirect("/login")
        
    user_id = session["user_id"]
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT prioridade, status, titulo FROM tarefas WHERE id=? AND usuario_id=?", (tarefa_id, user_id))
    res = c.fetchone()
    if res and res[1] == 'pendente':
        prio, titulo = res[0], res[2]
        recompensa = 20 if prio == 'Alta' else 10 if prio == 'Média' else 5
        c.execute("UPDATE tarefas SET status='concluida' WHERE id=?", (tarefa_id,))
        c.execute("UPDATE perfil SET cookies = cookies + ? WHERE usuario_id = ?", (recompensa, user_id))
        conn.commit()
        salvar_log(user_id, f"Concluiu a missão '{titulo}' (+{recompensa} Cookies).")
    conn.close()
    return redirect("/")

@app.route("/editar/<int:tarefa_id>", methods=["GET", "POST"])
def editar(tarefa_id):
    if "user_id" not in session:
        return redirect("/login")
        
    user_id = session["user_id"]
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    if request.method == "POST":
        titulo = request.form.get("titulo")
        descricao = request.form.get("descricao")
        data_limite = request.form.get("data_limite")
        prioridade = request.form.get("prioridade")
        categoria = request.form.get("categoria")
        c.execute("""
            UPDATE tarefas SET titulo=?, descricao=?, data_limite=?, prioridade=?, categoria=? 
            WHERE id=? AND usuario_id=?
        """, (titulo, descricao, data_limite, prioridade, categoria, tarefa_id, user_id))
        conn.commit()
        salvar_log(user_id, f"Editou os detalhes da missão '{titulo}'.")
        conn.close()
        return redirect("/")
    c.execute("SELECT id, titulo, descricao, status, data_limite, prioridade, categoria FROM tarefas WHERE id=? AND usuario_id=?", (tarefa_id, user_id))
    tarefa = c.fetchone()
    conn.close()
    return render_template("editar.html", tarefa=tarefa)

@app.route("/delete/<int:tarefa_id>", methods=["POST"])
def delete(tarefa_id):
    if "user_id" not in session:
        return redirect("/login")
        
    user_id = session["user_id"]
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT titulo FROM tarefas WHERE id=? AND usuario_id=?", (tarefa_id, user_id))
    res = c.fetchone()
    if res:
        titulo = res[0]
        c.execute("DELETE FROM tarefas WHERE id=? AND usuario_id=?", (tarefa_id, user_id))
        conn.commit()
        salvar_log(user_id, f"Excluiu a missão: '{titulo}'.")
    conn.close()
    return redirect("/")

if __name__ == "__main__":
    app.run(debug=True)
