from flask import Flask, render_template, request, send_file, flash, redirect, url_for
import pandas as pd
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Diretórios para uploads e resultados
UPLOAD_FOLDER = r'C:\Users\GuilhermeAraújoAguia\Desktop\TESTE_PY\uploads'
RESULT_FOLDER = r'C:\Users\GuilhermeAraújoAguia\Desktop\TESTE_PY\results'

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULT_FOLDER, exist_ok=True)

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        print("Recebendo arquivos...")  # Depuração para verificar se a função está sendo chamada
        if 'file1_fidc' in request.files and 'file2_fidc' in request.files:
            file1 = request.files['file1_fidc']
            file2 = request.files['file2_fidc']

            if file1.filename == '' or file2.filename == '':
                flash('Por favor, selecione ambos os arquivos.', 'danger')
                return redirect(request.url)

            print(f"Arquivo 1: {file1.filename}, Arquivo 2: {file2.filename}")
            result_path = process_files(file1, file2, 'FIDC_Juntos')

        else:
            flash('Por favor, selecione todos os arquivos necessários para upload.', 'danger')
            return redirect(request.url)

        if result_path and os.path.exists(result_path):
            print(f"Resultado gerado com sucesso: {result_path}")
            return send_file(result_path, as_attachment=True)
        else:
            print("Erro ao processar os arquivos para download.")
            flash('Erro ao processar os arquivos para download.', 'danger')
            return redirect(request.url)

    return render_template('index.html')

def process_files(file1, file2, fundo_name):
    try:
        path1 = os.path.join(UPLOAD_FOLDER, file1.filename)
        path2 = os.path.join(UPLOAD_FOLDER, file2.filename)
        file1.save(path1)
        file2.save(path2)
        print(f"Arquivos salvos em: {path1}, {path2}")
    except Exception as e:
        print(f"Erro ao salvar os arquivos: {e}")
        flash(f"Erro ao salvar os arquivos de upload: {str(e)}", 'danger')
        return None

    if not os.path.exists(path1) or not os.path.exists(path2):
        print(f"Arquivos não encontrados: {path1}, {path2}")
        flash(f"Erro ao salvar os arquivos de upload.", 'danger')
        return None

    # Carregar o arquivo Excel de retorno
    try:
        arquivo_retorno_df = pd.read_excel(path1, decimal=',', thousands='.')
        arquivo_retorno_df.dropna(how='all', inplace=True)
        print(f"Arquivo de retorno carregado com sucesso: {file1.filename}")
    except Exception as e:
        print(f"Erro ao ler o arquivo de retorno: {e}")
        flash(f"Erro ao ler o arquivo de retorno: {str(e)}", 'danger')
        return None

    # Carregar o arquivo Excel de Combine
    try:
        combine_df = pd.read_excel(path2, decimal=',', thousands='.')
        combine_df.dropna(how='all', inplace=True)
        print(f"Arquivo Combine carregado com sucesso: {file2.filename}")
    except Exception as e:
        print(f"Erro ao ler o arquivo Combine: {e}")
        flash(f"Erro ao ler o arquivo Combine: {str(e)}", 'danger')
        return None

    # Verificar se as colunas necessárias estão presentes
    required_columns_combine = ['CPF Cliente', 'Nome Cliente', 'FIDC', 'SEU NUMERO', 'CCB', 'Data Vencimento', 'Valor Nominal']
    required_columns_retorno = ['CPF', 'Valor Desconto']

    if not all(col in combine_df.columns for col in required_columns_combine):
        print("Colunas necessárias não encontradas no arquivo Combine.")
        flash(f"Colunas necessárias não encontradas no arquivo Combine.", 'danger')
        return None

    if not all(col in arquivo_retorno_df.columns for col in required_columns_retorno):
        print("Colunas necessárias não encontradas no arquivo de Retorno.")
        flash(f"Colunas necessárias não encontradas noa rquivo de Retorno.", 'danger')
        return None

    # Remover formatação de valores numéricos e garantir que são números nas colunas antes de concatenar
    try:
        combine_df['CPF Cliente'] = pd.to_numeric(combine_df['CPF Cliente'], errors='coerce').fillna(0).astype(int).astype(str)
        arquivo_retorno_df['CPF'] = pd.to_numeric(arquivo_retorno_df['CPF'], errors='coerce').fillna(0).astype(int).astype(str)

        combine_df['Valor Nominal'] = pd.to_numeric(combine_df['Valor Nominal'], errors='coerce').fillna(0)
        arquivo_retorno_df['Valor Desconto'] = pd.to_numeric(arquivo_retorno_df['Valor Desconto'], errors='coerce').fillna(0)
    except Exception as e:
        print(f"Erro ao processar os valores numéricos: {e}")
        flash(f"Erro ao processar os valores numéricos: {str(e)}", 'danger')
        return None 

    # Criar colunas chave para o cruzamento
    arquivo_retorno_df['Chave'] = arquivo_retorno_df['CPF'] + '-' + arquivo_retorno_df['Valor Desconto'].astype(str)
    combine_df['Chave'] = combine_df['CPF Cliente'] + '-' + combine_df['Valor Nominal'].astype(str)

    # Remover duplicatas com base na coluna "SEU NUMERO" 
    combine_df = combine_df.drop_duplicates(subset='SEU NUMERO', keep='first')

    # Identificar correspondências e filtrar o resultado final
    arquivo_retorno_df['Status'] = arquivo_retorno_df['Chave'].apply(
        lambda x: 'Conciliado' if x in combine_df['Chave'].values else 'Parciais'
    )
    conciliados = arquivo_retorno_df[arquivo_retorno_df['Status'] == 'Conciliado']
    parciais = arquivo_retorno_df[arquivo_retorno_df['Status'] == 'Parciais']

    # Converter a coluna "Valor Desconto" na aba "Parciais" para valores numéricos
    parciais['Valor Desconto'] = pd.to_numeric(parciais['Valor Desconto'], errors='coerce')

    # Fazer o merge do combine_df com o retorno para trazer a coluna 'Valor Nominal'
    merged_df = pd.merge(parciais, combine_df[['Chave', 'Valor Nominal']], on='Chave', how='left')

    # Atualizar status para inadimplente se o valor for igual a 0
    inadimplentes = merged_df[merged_df['Valor Desconto'] == 0]
    inadimplentes['Status'] = 'Inadimplente'

    # Remover as linhas que foram movidas para "Inadimplente" da aba "Parciais"
    parciais = merged_df[(merged_df['Valor Desconto'] != 0)]

    # Adicionar novas colunas: "CCB", "Originador" e "Status"
    resultado_df = pd.merge(combine_df[combine_df['Chave'].isin(conciliados['Chave'])], conciliados[['Chave', 'Valor Desconto']], on='Chave', how='left')
    resultado_df['CCB'] = resultado_df['SEU NUMERO'].astype(str).str[:8]
    resultado_df['Status'] = 'Conciliado'

    # Selecionar colunas para o resultado final, incluindo a coluna "Chave"
    resultado_final = resultado_df[['CPF Cliente', 'Nome Cliente', 'SEU NUMERO', 'CCB', 'Data Vencimento', 'Valor Desconto', 'FIDC', 'Convênio', 'Status', 'Chave']]

    # Remover duplicatas no resultado final com base na coluna "SEU NUMERO"
    resultado_final = resultado_final.drop_duplicates(subset='SEU NUMERO', keep='first')

    # Criar o nome do arquivo de download
    base_name = os.path.splitext(file1.filename)[0]
    result_filename = f"Base Baixas - {base_name}.xlsx"
    result_path = os.path.join(RESULT_FOLDER, result_filename)

    # Salvar os resultados em um arquivo Excel com duas abas: "Conciliado" e "Parciais"
    try:
        with pd.ExcelWriter(result_path) as writer:
            resultado_final.to_excel(writer, sheet_name='Conciliado', index=False)
            parciais.to_excel(writer, sheet_name='Parciais', index=False)
            inadimplentes.to_excel(writer, sheet_name='Inadimplente', index=False)
        print(f"Arquivo de resultados criado: {result_path}")
    except Exception as e:
        print(f"Erro ao criar o arquivo de resultados: {e}")
        flash(f"Erro ao criar o arquivo de resultados: {str(e)}", 'danger')
        return None

    return result_path if os.path.exists(result_path) else None

if __name__ == '__main__':
    app.run(debug=True)
