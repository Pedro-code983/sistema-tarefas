from flask import Flask, render_template, request, redirect, flash
import sqlite3

app = Flask(__name__)
app.secret_key = "roysse_secret_key"
DB_NAME = "database.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # Tabela de Tarefas
    c.execute("""
        CREATE TABLE IF NOT EXISTS tarefas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT NOT NULL,
            descricao TEXT,
            status TEXT DEFAULT 'pendente',
            data_limite TEXT,
            prioridade TEXT DEFAULT 'Média',
            categoria TEXT DEFAULT 'Geral'
        )
    """)
    # Tabela de Perfil
    c.execute("CREATE TABLE IF NOT EXISTS perfil (id INTEGER PRIMARY KEY, cookies INTEGER DEFAULT 0)")
    # Tabela da Loja
    c.execute("""
        CREATE TABLE IF NOT EXISTS loja (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            preco INTEGER NOT NULL,
            descricao TEXT
        )
    """)
    # NOVA: Tabela de Inventário (Itens Comprados)
    c.execute("""
        CREATE TABLE IF NOT EXISTS inventario (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            descricao TEXT
        )
    """)

    c.execute("INSERT OR IGNORE INTO perfil (id, cookies) VALUES (1, 0)")
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

@app.route("/", methods=["GET", "POST"])
def index():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    if request.method == "POST":
        titulo = request.form.get("titulo")
        descricao = request.form.get("descricao")
        data_limite = request.form.get("data_limite")
        prioridade = request.form.get("prioridade")
        categoria = request.form.get("categoria")
        if titulo:
            c.execute("INSERT INTO tarefas (titulo, descricao, data_limite, prioridade, categoria) VALUES (?, ?, ?, ?, ?)",
                      (titulo, descricao, data_limite, prioridade, categoria))
            conn.commit()
        return redirect("/")
    c.execute("SELECT * FROM tarefas ORDER BY CASE prioridade WHEN 'Alta' THEN 1 WHEN 'Média' THEN 2 ELSE 3 END")
    tarefas = c.fetchall()
    c.execute("SELECT cookies FROM perfil WHERE id = 1")
    saldo = c.fetchone()[0]
    conn.close()
    pendentes = len([t for t in tarefas if t[3] == 'pendente'])
    concluidas = len([t for t in tarefas if t[3] == 'concluida'])
    return render_template("index.html", tarefas=tarefas, pendentes=pendentes, concluidas=concluidas, cookies=saldo)

@app.route("/loja", methods=["GET", "POST"])
def loja():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    # Cadastro de novos mimos
    if request.method == "POST":
        nome = request.form.get("nome")
        preco = request.form.get("preco")
        descricao = request.form.get("descricao")
        if nome and preco:
            c.execute("INSERT INTO loja (nome, preco, descricao) VALUES (?, ?, ?)", (nome, preco, descricao))
            conn.commit()
        return redirect("/loja")

    c.execute("SELECT * FROM loja")
    itens = c.fetchall()
    
    # Busca itens comprados no inventário
    c.execute("SELECT * FROM inventario ORDER BY id DESC")
    meus_itens = c.fetchall()
    
    c.execute("SELECT cookies FROM perfil WHERE id = 1")
    saldo = c.fetchone()[0]
    conn.close()
    return render_template("loja.html", itens=itens, cookies=saldo, meus_itens=meus_itens)

@app.route("/comprar/<int:item_id>", methods=["POST"])
def comprar(item_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT preco, nome, descricao FROM loja WHERE id=?", (item_id,))
    res_item = c.fetchone()
    c.execute("SELECT cookies FROM perfil WHERE id=1")
    res_saldo = c.fetchone()

    if res_item and res_saldo:
        preco, nome, descricao = res_item[0], res_item[1], res_item[2]
        saldo = res_saldo[0]

        if saldo >= preco:
            # Subtrai cookies
            c.execute("UPDATE perfil SET cookies = cookies - ? WHERE id=1", (preco,))
            # Adiciona ao inventário
            c.execute("INSERT INTO inventario (nome, descricao) VALUES (?, ?)", (nome, descricao))
            conn.commit()
            flash(f"Sucesso! Você resgatou: {nome}", "success")
        else:
            flash(f"Saldo insuficiente para {nome}!", "error")
            
    conn.close()
    return redirect("/loja")

# ... (outras rotas concluir, editar, delete permanecem iguais)
@app.route("/concluir/<int:tarefa_id>", methods=["POST"])
def concluir(tarefa_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT prioridade, status FROM tarefas WHERE id=?", (tarefa_id,))
    res = c.fetchone()
    if res and res[1] == 'pendente':
        prio = res[0]
        recompensa = 20 if prio == 'Alta' else 10 if prio == 'Média' else 5
        c.execute("UPDATE tarefas SET status='concluida' WHERE id=?", (tarefa_id,))
        c.execute("UPDATE perfil SET cookies = cookies + ? WHERE id = 1", (recompensa,))
        conn.commit()
    conn.close()
    return redirect("/")

@app.route("/editar/<int:tarefa_id>", methods=["GET", "POST"])
def editar(tarefa_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    if request.method == "POST":
        titulo = request.form.get("titulo")
        descricao = request.form.get("descricao")
        data_limite = request.form.get("data_limite")
        prioridade = request.form.get("prioridade")
        categoria = request.form.get("categoria")
        c.execute("UPDATE tarefas SET titulo=?, descricao=?, data_limite=?, prioridade=?, categoria=? WHERE id=?", 
                  (titulo, descricao, data_limite, prioridade, categoria, tarefa_id))
        conn.commit()
        conn.close()
        return redirect("/")
    c.execute("SELECT * FROM tarefas WHERE id=?", (tarefa_id,))
    tarefa = c.fetchone()
    conn.close()
    return render_template("editar.html", tarefa=tarefa)

@app.route("/delete/<int:tarefa_id>", methods=["POST"])
def delete(tarefa_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM tarefas WHERE id=?", (tarefa_id,))
    conn.commit()
    conn.close()
    return redirect("/")

if __name__ == "__main__":
    app.run(debug=True)
