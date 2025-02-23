from flask import Flask, render_template, request, redirect, url_for, session
from flask_pymongo import PyMongo
from werkzeug.security import generate_password_hash, check_password_hash
from bson.objectid import ObjectId
import pandas as pd
from io import BytesIO
from flask import send_file


app = Flask(__name__)

# Configuração MongoDB
app.config["MONGO_URI"] = "mongodb+srv://financas:65234512@financas.go1tt.mongodb.net/financas"
mongo = PyMongo(app)

# Configuração de sessão
app.secret_key = "super_secret_key"

# Rotas de autenticação
@app.route('/')
def home():
    if "user" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        telefone = request.form['telefone']
        senha = request.form['senha']
        user = mongo.db.usuarios.find_one({"telefone": telefone})

        if user and check_password_hash(user['senha'], senha):
            session['user'] = user['nome']
            return redirect(url_for('dashboard'))
        else:
            return "Usuário ou senha incorretos", 401
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        nome = request.form['nome']
        telefone = request.form['telefone']
        senha = request.form['senha']

        if len(senha) < 4:
            return "Senha deve ter no mínimo 4 caracteres", 400

        hash_senha = generate_password_hash(senha)
        mongo.db.usuarios.insert_one({"nome": nome, "telefone": telefone, "senha": hash_senha})
        return redirect(url_for('login'))
    return render_template('signup.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

# Dashboard
@app.route('/dashboard', methods=['GET'])
def dashboard():
    if "user" not in session:
        return redirect(url_for("login"))

    # Recupera bancos e calcula o saldo total
    bancos = list(mongo.db.bancos.find())
    total_saldo = sum([banco['saldo'] for banco in bancos])

    # Recupera transações
    transacoes = list(mongo.db.transacoes.find())

    # Calcula despesas e entradas totais
    total_despesas = sum([transacao['valor'] for transacao in transacoes if transacao['tipo'] == 'Saída'])
    total_entradas = sum([transacao['valor'] for transacao in transacoes if transacao['tipo'] == 'Entrada'])

    return render_template(
        'dashboard.html',
        user=session['user'],
        total_saldo=total_saldo,
        total_despesas=total_despesas,
        total_entradas=total_entradas
    )


# Adicionar Transação
@app.route('/add_transaction', methods=['GET', 'POST'])
def add_transaction():
    if "user" not in session:
        return redirect(url_for("login"))

    if request.method == 'POST':
        descricao = request.form['descricao']
        valor = float(request.form['valor'])
        tipo = request.form['tipo']
        topico = request.form['topico']
        
        # Se o campo banco estiver vazio, ele será None
        banco_id = request.form['banco'] if request.form.get('banco') else None
        cartao_id = request.form['cartao'] if request.form.get('cartao') else None

        # Buscar banco e cartão de crédito com base no ID
        banco = mongo.db.bancos.find_one({"_id": ObjectId(banco_id)}) if banco_id else None
        cartao = mongo.db.cartoes.find_one({"_id": ObjectId(cartao_id)}) if cartao_id else None

        # Verifica e ajusta o saldo do banco ou o limite do cartão
        if tipo == "Saída":
            if banco:
                banco['saldo'] -= valor
            if cartao:
                cartao['limite'] -= valor
        elif tipo == "Entrada":
            if banco:
                banco['saldo'] += valor
            if cartao:
                cartao['limite'] += valor

        # Atualizar banco e cartão no MongoDB
        if banco:
            mongo.db.bancos.update_one({"_id": ObjectId(banco_id)}, {"$set": {"saldo": banco['saldo']}})
        if cartao:
            mongo.db.cartoes.update_one({"_id": ObjectId(cartao_id)}, {"$set": {"limite": cartao['limite']}})

        # Capturar a data da transação
        data_transacao = request.form['data']

        # Inserir a transação no MongoDB
        mongo.db.transacoes.insert_one({
            "descricao": descricao,
            "valor": valor,
            "tipo": tipo,
            "topico": topico,
            "banco": banco_id if banco else None,
            "cartao": cartao_id if cartao else None,
            "data": data_transacao
        })

        return redirect(url_for("dashboard"))

    # Se o método for GET, renderiza o formulário
    bancos = mongo.db.bancos.find()
    cartoes = mongo.db.cartoes.find()
    topicos = mongo.db.topicos.find()
    return render_template('add_transaction.html', bancos=bancos, cartoes=cartoes, topicos=topicos)


# Gerenciar Bancos
@app.route('/view_banks', methods=['GET', 'POST'])
def view_banks():
    if "user" not in session:
        return redirect(url_for("login"))

    if request.method == 'POST':
        nome_banco = request.form['nome_banco']
        saldo_inicial = float(request.form['saldo_inicial'])

        mongo.db.bancos.insert_one({"nome": nome_banco, "saldo": saldo_inicial})
        return redirect(url_for("view_banks"))

    bancos = mongo.db.bancos.find()
    return render_template('view_banks.html', bancos=bancos)

@app.route('/add_bank', methods=['POST'])
def add_bank():
    if "user" not in session:
        return redirect(url_for("login"))

    nome_banco = request.form['nome_banco']
    saldo_inicial = float(request.form['saldo_inicial'])

    # Inserir o banco no MongoDB
    mongo.db.bancos.insert_one({"nome": nome_banco, "saldo": saldo_inicial})
    return redirect(url_for("view_banks"))

@app.route('/delete_bank/<bank_id>', methods=['POST'])
def delete_bank(bank_id):
    if "user" not in session:
        return redirect(url_for("login"))

    # Remove o banco do MongoDB
    mongo.db.bancos.delete_one({"_id": ObjectId(bank_id)})
    return redirect(url_for("view_banks"))

@app.route('/edit_bank/<bank_id>', methods=['GET', 'POST'])
def edit_bank(bank_id):
    if "user" not in session:
        return redirect(url_for("login"))

    if request.method == 'GET':
        # Exibir o formulário de edição
        banco = mongo.db.bancos.find_one({"_id": ObjectId(bank_id)})
        return render_template('edit_bank.html', banco=banco)

    elif request.method == 'POST':
        # Salvar alterações no banco
        nome_banco = request.form['nome_banco']
        saldo = float(request.form['saldo'])

        # Atualiza os dados no MongoDB
        mongo.db.bancos.update_one(
            {"_id": ObjectId(bank_id)},
            {"$set": {"nome": nome_banco, "saldo": saldo}}
        )
        return redirect(url_for("view_banks"))



# Gerenciar Tópicos
@app.route('/manage_topics', methods=['GET', 'POST'])
def manage_topics():
    if "user" not in session:
        return redirect(url_for("login"))

    if request.method == 'POST':
        nome_topico = request.form['nome_topico']
        cor_topico = request.form['cor_topico']

        mongo.db.topicos.insert_one({"nome": nome_topico, "cor": cor_topico})
        return redirect(url_for("manage_topics"))

    topicos = mongo.db.topicos.find()
    return render_template('manage_topics.html', topicos=topicos)


@app.route('/add_topic', methods=['POST'])
def add_topic():
    if "user" not in session:
        return redirect(url_for("login"))

    nome_topico = request.form['nome_topico']
    cor_topico = request.form['cor_topico']

    # Adiciona o tópico no banco de dados MongoDB
    mongo.db.topicos.insert_one({"nome": nome_topico, "cor": cor_topico})
    return redirect(url_for("manage_topics"))


@app.route('/delete_topic/<topic_id>', methods=['POST'])
def delete_topic(topic_id):
    if "user" not in session:
        return redirect(url_for("login"))

    # Remove o tópico do MongoDB
    mongo.db.topicos.delete_one({"_id": ObjectId(topic_id)})
    return redirect(url_for("manage_topics"))

@app.route('/registro_transacoes', methods=['GET'])
def registro_transacoes():
    if "user" not in session:
        return redirect(url_for("login"))

    # Pega o número da página (default é 1)
    pagina = int(request.args.get('pagina', 1))
    limite = 10  # Número de registros por página
    skip = (pagina - 1) * limite

    # Busca todas as transações paginadas
    transacoes = list(mongo.db.transacoes.find().skip(skip).limit(limite))

    # Criar um dicionário com nomes dos bancos
    bancos = {b["_id"]: b["nome"] for b in mongo.db.bancos.find()}
    
    # Substituir banco ID pelo nome no resultado
    for transacao in transacoes:
        transacao["banco"] = bancos.get(ObjectId(transacao["banco"]), "Banco não encontrado")

    # Conta o total de transações
    total_transacoes = mongo.db.transacoes.count_documents({})
    total_paginas = (total_transacoes + limite - 1) // limite  # Calcula páginas totais

    return render_template(
        'registro_transacoes.html',
        transacoes=transacoes,
        pagina=pagina,
        total_paginas=total_paginas
    )


@app.route('/edit_transaction/<transaction_id>', methods=['GET', 'POST'])
def edit_transaction(transaction_id):
    if "user" not in session:
        return redirect(url_for("login"))

    if request.method == 'POST':
        # Atualizar a transação
        descricao = request.form['descricao']
        valor = float(request.form['valor'])
        tipo = request.form['tipo']
        topico = request.form['topico']
        banco_id = request.form['banco']

        mongo.db.transacoes.update_one(
            {"_id": ObjectId(transaction_id)},
            {"$set": {
                "descricao": descricao,
                "valor": valor,
                "tipo": tipo,
                "topico": topico,
                "banco": banco_id
            }}
        )
        return redirect(url_for("registro_transacoes"))

    # Recuperar dados da transação
    transacao = mongo.db.transacoes.find_one({"_id": ObjectId(transaction_id)})
    bancos = mongo.db.bancos.find()
    topicos = mongo.db.topicos.find()
    return render_template('edit_transaction.html', transacao=transacao, bancos=bancos, topicos=topicos)


@app.route('/delete_transaction/<transaction_id>', methods=['POST'])
def delete_transaction(transaction_id):
    if "user" not in session:
        return redirect(url_for("login"))

    mongo.db.transacoes.delete_one({"_id": ObjectId(transaction_id)})
    return redirect(url_for("registro_transacoes"))


@app.route('/filtros', methods=['GET', 'POST'])
def filtros():
    if "user" not in session:
        return redirect(url_for("login"))

    resultados = []
    saldo_acumulado = 0

    if request.method == 'POST':
        criterio = request.form.get('criterio', '').strip()
        tipo_filtro = request.form.get('tipo_filtro', 'descricao')

        # Busca as transações com base no filtro
        query = {}
        if tipo_filtro == 'descricao':
            query = {"descricao": {"$regex": criterio, "$options": "i"}} if criterio else {}
        elif tipo_filtro == 'topico':
            query = {"topico": {"$regex": criterio, "$options": "i"}} if criterio else {}

        # Realiza a busca no MongoDB
        resultados = list(mongo.db.transacoes.find(query))

        # Criar um dicionário com nomes dos bancos
        bancos = {b["_id"]: b["nome"] for b in mongo.db.bancos.find()}

        # Substituir banco ID pelo nome no resultado e calcular saldo acumulado
        for transacao in resultados:
            transacao["banco"] = bancos.get(ObjectId(transacao["banco"]), "Banco não encontrado")
            if transacao['tipo'] == 'Entrada':
                saldo_acumulado += transacao['valor']
            elif transacao['tipo'] == 'Saída':
                saldo_acumulado -= transacao['valor']

    return render_template(
        'filtros.html',
        resultados=resultados,
        saldo_acumulado=saldo_acumulado
    )

@app.route('/backup', methods=['GET'])
def backup():
    if "user" not in session:
        return redirect(url_for("login"))

    # Busca os dados do MongoDB
    bancos = list(mongo.db.bancos.find())
    transacoes = list(mongo.db.transacoes.find())
    topicos = list(mongo.db.topicos.find())

    # Criar DataFrames para cada coleção
    bancos_df = pd.DataFrame(bancos)
    transacoes_df = pd.DataFrame(transacoes)
    topicos_df = pd.DataFrame(topicos)

    # Salvar em um arquivo Excel
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        bancos_df.to_excel(writer, index=False, sheet_name='Bancos')
        transacoes_df.to_excel(writer, index=False, sheet_name='Transacoes')
        topicos_df.to_excel(writer, index=False, sheet_name='Topicos')
    output.seek(0)

    return send_file(
        output,
        as_attachment=True,
        download_name='backup_financas.xlsx',
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )


@app.route('/restaurar_dados', methods=['GET', 'POST'])
def restaurar_dados():
    if "user" not in session:
        return redirect(url_for("login"))

    if request.method == 'POST':
        # Verifica se um arquivo foi enviado
        if 'file' not in request.files:
            return "Nenhum arquivo enviado", 400
        file = request.files['file']

        if file.filename == '':
            return "Nenhum arquivo selecionado", 400

        if file:
            # Lê o arquivo Excel enviado
            data = pd.read_excel(file, sheet_name=None)

            # Limpa as coleções existentes
            mongo.db.bancos.delete_many({})
            mongo.db.transacoes.delete_many({})
            mongo.db.topicos.delete_many({})

            # Insere os dados restaurados
            if 'Bancos' in data:
                bancos = data['Bancos'].to_dict(orient='records')
                mongo.db.bancos.insert_many(bancos)

            if 'Transacoes' in data:
                transacoes = data['Transacoes'].to_dict(orient='records')
                mongo.db.transacoes.insert_many(transacoes)

            if 'Topicos' in data:
                topicos = data['Topicos'].to_dict(orient='records')
                mongo.db.topicos.insert_many(topicos)

            return redirect(url_for('dashboard'))

    return render_template('restaurar_dados.html')

# Gerenciar Cartões de Crédito
@app.route('/view_cards', methods=['GET', 'POST'])
def view_cards():
    if "user" not in session:
        return redirect(url_for("login"))

    if request.method == 'POST':
        nome_banco = request.form['nome_banco']
        limite = float(request.form['limite'])
        numero_cartao = request.form['numero_cartao']
        data_vencimento = request.form['data_vencimento']

        mongo.db.cartoes.insert_one({
            "nome_banco": nome_banco, 
            "limite": limite, 
            "numero_cartao": numero_cartao, 
            "data_vencimento": data_vencimento
        })
        return redirect(url_for("view_cards"))

    # Exibir cartões de crédito cadastrados
    cartoes = mongo.db.cartoes.find()
    return render_template('view_cards.html', cartoes=cartoes)


@app.route('/edit_card/<card_id>', methods=['GET', 'POST'])
def edit_card(card_id):
    if "user" not in session:
        return redirect(url_for("login"))

    if request.method == 'POST':
        nome_banco = request.form['nome_banco']
        limite = float(request.form['limite'])
        numero_cartao = request.form['numero_cartao']
        data_vencimento = request.form['data_vencimento']

        # Atualiza as informações do cartão no banco de dados
        mongo.db.cartoes.update_one(
            {"_id": ObjectId(card_id)},
            {"$set": {
                "nome_banco": nome_banco, 
                "limite": limite, 
                "numero_cartao": numero_cartao, 
                "data_vencimento": data_vencimento
            }}
        )
        return redirect(url_for("view_cards"))

    # Exibir o formulário de edição
    card = mongo.db.cartoes.find_one({"_id": ObjectId(card_id)})
    return render_template('edit_card.html', card=card)


@app.route('/delete_card/<card_id>', methods=['POST'])
def delete_card(card_id):
    if "user" not in session:
        return redirect(url_for("login"))

    # Remove o cartão do MongoDB
    mongo.db.cartoes.delete_one({"_id": ObjectId(card_id)})
    return redirect(url_for("view_cards"))

from flask import flash, render_template, redirect, url_for, request
from bson import ObjectId

@app.route('/delete_all', methods=['GET', 'POST'])
def delete_all():
    if "user" not in session:
        return redirect(url_for("login"))
    
    if request.method == 'POST':
        # Deletar tudo do MongoDB
        mongo.db.bancos.delete_many({})
        mongo.db.transacoes.delete_many({})
        mongo.db.topicos.delete_many({})
        mongo.db.cartoes.delete_many({})

        flash("Todos os dados foram deletados com sucesso!", "success")
        return redirect(url_for("dashboard"))

    return render_template('delete_all.html')



# Configurações
@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if "user" not in session:
        return redirect(url_for("login"))

    if request.method == 'POST':
        # Aqui seria salvo no MongoDB as configurações personalizadas do usuário
        return redirect(url_for("dashboard"))

    return render_template('settings.html')

if __name__ == '__main__':
    app.run(debug=True)

#------------------------------------------------------------------------------
