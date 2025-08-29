import pandas as pd
import numpy as np
import streamlit as st
import datetime
from io import BytesIO
import re

class CalculandoTaxadeGestao:
    def __init__(self):
        self.planilha_controle = None   # corrigido nome do atributo
        self.pl_data = []

    def load_control_file(self, uploaded_planilha_de_controle):
        """Load the control spreadsheet's BTG tab."""
        try:
            self.planilha_controle = pd.read_excel(uploaded_planilha_de_controle, sheet_name=1, skiprows=1)
            # Process 'Conta' column as in original code
            self.planilha_controle['Conta'] = self.planilha_controle['Conta'].astype(str).str[:-2].map(lambda x: '00' + x)
            self.planilha_controle = self.planilha_controle[['Conta', 'Taxa de Gestão']]
            # Handle specific accounts with extra zero
            contas_3_zeros = [
                '00989247', '00938440', '00626491', '00806386',
                '00431814', '00827730', '00772433', '00834301', '00330949'
            ]
            contas_add_zero = self.planilha_controle[self.planilha_controle['Conta'].isin(contas_3_zeros)].reset_index()
            contas_add_zero['Conta'] = contas_add_zero['Conta'].apply(lambda x: '0' + x)
            self.planilha_controle = pd.concat([self.planilha_controle, contas_add_zero])
            self.planilha_controle.rename(columns={'Taxa de Gestão': 'Taxa_de_Gestão', 'Conta': 'conta'}, inplace=True)
        except Exception as e:
            st.error(f"Erro ao carregar planilha de controle: {e}")

    def load_pl_file(self, uploaded_pl, file_name):
        """Load a PL file and extract date from file name."""
        try:
            # Extract date from file name (e.g., 'PL Total - 31.07.xlsx' -> '31.07')
            match = re.search(r'PL Total - (\d{2}\.\d{2})', file_name)
            if not match:
                st.error(f"Nome do arquivo '{file_name}' não contém data no formato 'PL Total - DD.MM'. Pulando arquivo.")
                return
            date_str = match.group(1)  # e.g., '31.07'
            # Convert to datetime for internal use
            try:
                date = datetime.datetime.strptime(date_str, '%d.%m').replace(year=datetime.date.today().year)
            except ValueError:
                st.error(f"Data inválida no nome do arquivo '{file_name}'. Use o formato 'PL Total - DD.MM'. Pulando arquivo.")
                return

            pl = pd.read_excel(uploaded_pl)
            pl = pl[['Conta', 'Valor']].rename(columns={'Conta': 'conta', 'Valor': 'VALOR'})
            pl['Data'] = date
            self.pl_data.append(pl)
        except Exception as e:
            st.error(f"Erro ao carregar arquivo PL '{file_name}': {e}")

    def calculate_daily_fees(self):
        """Calculate daily management fees and pivot to daily columns."""
        if (
            self.planilha_controle is None
            or not isinstance(self.planilha_controle, pd.DataFrame)
            or self.planilha_controle.empty
            or len(self.pl_data) == 0
        ):
            st.error("Planilha de controle ou arquivos PL não carregados.")
            return None

        # Combine all PL data
        pl_combined = pd.concat(self.pl_data, ignore_index=True)
        calculo_diario = 1/252

        # Merge control and PL data
        tx_gestao = pd.merge(self.planilha_controle, pl_combined, left_on='conta', right_on='conta', how='outer')
        tx_gestao = tx_gestao[['conta', 'Taxa_de_Gestão', 'VALOR', 'Data']].dropna(subset=['conta'])

        # Calculate daily management fee
        tx_gestao['Tx_Gestão_Diaria'] = ((tx_gestao['Taxa_de_Gestão'] + 1) ** calculo_diario - 1) * 100
        tx_gestao['Valor_de_cobrança'] = round(tx_gestao['VALOR'] * (tx_gestao['Tx_Gestão_Diaria']) / 100, 2)

        # Format date as DD.MM
        tx_gestao['Data'] = pd.to_datetime(tx_gestao['Data']).dt.strftime('%d.%m')

        # Pivot to create daily columns
        pivot_table = tx_gestao.pivot_table(
            values='Valor_de_cobrança',
            index='conta',
            columns='Data',
            aggfunc='sum'
        ).reset_index()

        # Add a Total column summing all daily fees
        numeric_columns = pivot_table.select_dtypes(include=[np.number]).columns
        pivot_table['Total'] = pivot_table[numeric_columns].sum(axis=1).round(2)

        return pivot_table

    def to_excel(self, df):
        """Convert DataFrame to Excel for download."""
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Taxa_Gestao_Diaria')
        return output.getvalue()

def main():
    st.title("Cálculo de Taxa de Gestão Diária - BTG")
    calculadora = CalculandoTaxadeGestao()

    # Upload control spreadsheet
    uploaded_control = st.file_uploader("Carregar Planilha de Controle (BTG)", type=['xlsx'])
    if uploaded_control:
        calculadora.load_control_file(uploaded_control)
        st.success("Planilha de controle carregada com sucesso!")

    # Upload multiple PL files
    uploaded_pls = st.file_uploader("Carregar Arquivos PL", type=['xlsx'], accept_multiple_files=True)
    if uploaded_pls:
        for pl_file in uploaded_pls:
            calculadora.load_pl_file(pl_file, pl_file.name)
        st.success("Arquivos PL carregados com sucesso!")

    # Calculate and display results
    if st.button("Calcular Taxas Diárias"):
        result = calculadora.calculate_daily_fees()
        if result is not None:
            st.dataframe(result)
            # Offer download
            excel_data = calculadora.to_excel(result)
            st.download_button(
                label="Baixar Resultado em Excel",
                data=excel_data,
                file_name="taxa_gestao_diaria.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

if __name__ == "__main__":
    main()
