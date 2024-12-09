import streamlit as st
import os
import pyodbc
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from PIL import Image
from typing import List, Optional, Dict, Any
from datetime import datetime


# Set page config di bagian paling atas
st.set_page_config(layout="wide", page_title="Dashboard SLA Maintenance HMS")

# User credentials untuk login
USER_CREDENTIALS = {
    "admin": "fleet123",
    "user": "fleetho"
}

def verify_login(username, password):
    """
    Memeriksa apakah username dan password cocok dengan yang ada di USER_CREDENTIALS
    """
    return USER_CREDENTIALS.get(username) == password

# Halaman Login
def login_page():
    st.title("Login")
    st.write("Silakan masukkan username dan password untuk masuk.")

    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login")

        if submit:
            if verify_login(username, password):
                # Menyimpan status login ke session_state
                st.session_state["logged_in"] = True
                st.session_state["username"] = username
                st.success("Login berhasil!")
                st.rerun()  # Pindah ke dashboard
            else:
                st.error("Username atau password salah!")
# Cek apakah user sudah login
if "logged_in" not in st.session_state or not st.session_state["logged_in"]:
    login_page()  # Tampilkan halaman login jika belum login
else:
    class DatabaseConnection:
        def __init__(self, server: str, database: str, username: str, password: str, driver: str):
            """
            Inisialisasi parameter koneksi database
            """
            self.connection_string = (
                f'DRIVER={{{driver}}};'
                f'SERVER={server};'
                f'DATABASE={database};'
                f'UID={username};'
                f'PWD={password};'
                'TrustServerCertificate=yes'
            )
        
        def fetch_data(self, query: str) -> Optional[pd.DataFrame]:
            """
            Ambil data dari database menggunakan query yang diberikan
            """
            try:
                conn = pyodbc.connect(self.connection_string)
                data = pd.read_sql_query(query, conn)
                return data
            except pyodbc.Error as e:
                st.error(f"Error koneksi: {e}")
                return None
            finally:
                if 'conn' in locals() and conn is not None:
                    conn.close()

    class SLADashboard:
        def __init__(self, db_connection: DatabaseConnection):
            """
            Inisialisasi Dashboard SLA
            """
            self.db_connection = db_connection
            self.setup_page()
            # Inisialisasi state untuk cache data
            if 'last_refresh_time' not in st.session_state:
                st.session_state.last_refresh_time = datetime.now()
            
            # Inisialisasi cache untuk data
            if 'sla_data' not in st.session_state:
                st.session_state.sla_data = {
                    'results': {},
                    'branch_results': {},
                    'data_detail': None
                }
        
        def setup_page(self):
            """Konfigurasi tata letak dan judul halaman Streamlit"""
            
            # Muat logo
            try:
                image = Image.open('logo-assa.png')
            except FileNotFoundError:
                st.warning("File logo tidak ditemukan")
                image = None
            
            # Header halaman
            col1, col2, col3 = st.columns([0.1, 0.8, 0.1])
            with col1:
                if image:
                    st.image(image, width=150)
            
            with col2:
                html_title = """
                    <style>
                    .title-test {
                    font-weight:bold;
                    padding:5px;
                    border-radius:6px;
                    }
                    </style>
                    <center><h1 class="title-test">Dashboard SLA Maintenance HMS</h1></center>"""
                st.markdown(html_title, unsafe_allow_html=True)

            with col3:
                if st.button("🔄 Refresh Data", key="unique_refresh_button"):
                    self.refresh_data()    
        def refresh_data(self):
            """
            Refresh semua data pada dashboard
            """
            # Reset cache data
            st.session_state.sla_data = {
                'results': {},
                'branch_results': {},
                'data_detail': None
            }
            
            # Update waktu refresh terakhir
            st.session_state.last_refresh_time = datetime.now()
            
            # Tampilkan pesan sukses
            st.success(f"Data berhasil diperbarui pada {st.session_state.last_refresh_time.strftime('%d-%m-%Y %H:%M:%S')}")
            
            # Gunakan st.rerun() sebagai pengganti experimental_rerun()
            st.rerun()

            # Menampilkan tombol logout
        if st.button("Logout", key="unique_logout_button"):
            st.session_state.logged_in = False
            if "role" in st.session_state:
                del st.session_state["role"]  # Hapus role jika ada
            st.rerun()  # Refresh halaman untuk kembali ke login page


        def fetch_or_get_cached_data(self, queries: Dict[str, str], is_branch_query: bool = False, branch_filter: str = "") -> Dict[str, pd.DataFrame]:
            try:
                # Tambahkan branch_filter sebagai parameter untuk membedakan cache
                cache_key = f'branch_results_{branch_filter}' if is_branch_query else f'results_{branch_filter}'
                
                # Jika data sudah ada di cache, kembalikan
                if cache_key in st.session_state.sla_data and st.session_state.sla_data[cache_key]:
                    return st.session_state.sla_data[cache_key]
                
                # Jika belum, ambil data dari database
                fetched_data = {}
                for key, query in queries.items():
                    # Tambahkan branch_filter ke dalam query
                    modified_query = query.replace('{branch_filter}', branch_filter)
                    data = self.db_connection.fetch_data(modified_query)
                    
                    if data is not None and not data.empty:
                        fetched_data[key] = data
                    else:
                        st.warning(f"Tidak ada data untuk query {key}")
                        fetched_data[key] = pd.DataFrame()
                
                # Simpan ke cache dengan key baru
                st.session_state.sla_data[cache_key] = fetched_data
                
                return fetched_data
            except Exception as e:
                st.error(f"Terjadi kesalahan saat mengambil data: {e}")
                return {}
        @st.cache_data
        def fetch_data_cached(self, query: str):
            return self.db_connection.fetch_data(query)

        def create_sidebar_filters(self) -> Dict[str, Any]:
            """
            Buat filter sidebar untuk pemilihan cabang
            """
            st.sidebar.title("Filter Data")
            
            # Ambil daftar cabang
            query_cabang = "SELECT DISTINCT Nama_Cabang FROM SLA_HMS"
            data_cabang = self.db_connection.fetch_data(query_cabang)
            
            cabang_list = ['All']
            if data_cabang is not None:
                sorted_cabang = sorted(data_cabang['Nama_Cabang'].tolist())
                cabang_list += sorted_cabang
            
            selected_cabang = st.sidebar.multiselect(
                "Pilih Cabang", 
                options=cabang_list, 
                default="All" if "All" in cabang_list else None
            )
            
            return {
                'selected_cabang': selected_cabang
            }
        
        def generate_branch_filter_sql(self, selected_cabang: List[str]) -> str:
            """
            Hasilkan filter SQL untuk cabang
            """
            # Jika "All" dipilih atau tidak ada pilihan, kembalikan string kosong
            if not selected_cabang or "All" in selected_cabang:
                return ""
            
            # Buat filter untuk cabang yang dipilih
            branch_filter = f"AND Nama_Cabang IN ({', '.join(f"'{cabang}'" for cabang in selected_cabang)})"
            return branch_filter
        
        def create_gauge_chart(self, title: str, value: float) -> go.Figure:
            """
            Buat gauge chart untuk persentase SLA
            """
            fig = go.Figure(go.Indicator(
                mode="gauge+number",
                value=value,
                number={'suffix': "%"},
                title={'text': title},
                gauge={
                    'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': "darkblue"},
                    'bar': {'color': "lightgreen"},
                    'steps': [
                        {'range': [0, 50], 'color': "red"},
                        {'range': [50, 80], 'color': "orange"},
                        {'range': [80, 100], 'color': "green"}
                    ],
                }
            ))
            fig.update_layout(margin=dict(t=50, b=0, l=0, r=0), height=250)
            return fig
        
        def prepare_categorical_data(self, data: pd.DataFrame, category_column: str) -> pd.DataFrame:
            """
            Siapkan data kategorik untuk grafik batang
            """
            # Temukan nama kolom yang sesuai tanpa memperhatikan kapitalisasi
            matching_column = None
            for col in data.columns:
                if col.lower() == category_column.lower():
                    matching_column = col
                    break
            
            if matching_column is None:
                st.warning(f"Kolom {category_column} tidak ditemukan dalam data")
                return data
            
            # Gunakan nama kolom yang cocok
            data[matching_column] = data[matching_column].apply(lambda x: 'OK' if str(x).upper() == 'OK' else 'NOT OK')
            return data
        
        def create_bar_chart(self, data: pd.DataFrame, title: str, category_column: str) -> go.Figure:
            """
            Buat grafik batang tumpuk untuk kinerja SLA per cabang
            """
            # Temukan nama kolom yang sesuai tanpa memperhatikan kapitalisasi
            matching_column = None
            for col in data.columns:
                if col.lower() == category_column.lower():
                    matching_column = col
                    break
            
            if matching_column is None:
                st.warning(f"Kolom {category_column} tidak ditemukan dalam data")
                return go.Figure()
            
            fig = px.bar(data,
                x='Nama_Cabang',
                y='persentase',
                color=matching_column,
                barmode='stack',
                title=title,
                labels={'persentase': 'Persentase', 'Nama_Cabang': 'Cabang'},
                color_discrete_map={'OK': 'lightgreen', 'NOT OK': 'red'}
            )
            fig.update_layout(
                xaxis={'categoryorder': 'total descending'},
                height=400
            )
            return fig
        
        def run_dashboard(self):
            """
            Metode utama untuk menjalankan Dashboard SLA
            """
            # Tampilkan waktu refresh terakhir
            st.sidebar.info(f"Terakhir diperbarui: {st.session_state.last_refresh_time.strftime('%d-%m-%Y %H:%M:%S')}")
            
            # Dapatkan filter
            filters = self.create_sidebar_filters()
            branch_filter = self.generate_branch_filter_sql(filters['selected_cabang'])
        
            
            # Query untuk data SLA
            queries = {
                'accu': f"""
                    SELECT 
                        ROUND((SUM(CASE WHEN Status_ACCU = 'OK' THEN 1 END) * 1.0 / COUNT(*)), 3) AS persentase
                    FROM SLA_HMS
                    WHERE 1=1 {branch_filter}
                """,
                'kopling': f"""
                    SELECT 
                        ROUND((SUM(CASE WHEN Status_Kopling = 'OK' THEN 1 END) * 1.0 / COUNT(*)), 3) AS persentase
                    FROM SLA_HMS
                    WHERE tipe_transmisi <> 'A/T' {branch_filter}
                """,
                'pb': f"""
                    SELECT 
                        ROUND((SUM(CASE WHEN Status_PB = 'OK' THEN 1 END) * 1.0 / COUNT(*)), 3) AS persentase
                    FROM SLA_HMS
                    WHERE 1=1 {branch_filter}
                """,
                'ban': f"""
                    SELECT 
                        ROUND((SUM(CASE WHEN Status_Ban = 'OK' THEN 1 END) * 1.0 / COUNT(*)), 3) AS persentase
                    FROM SLA_HMS
                    WHERE 1=1 {branch_filter}
                """
            }
            
            # Query untuk data per cabang
            branch_queries = {
                'accu': f"""
                    SELECT 
                        Nama_Cabang,
                        Status_ACCU,
                        ROUND(
                            (COUNT(*) * 1.0 / SUM(COUNT(*)) OVER (PARTITION BY Nama_Cabang)) * 100, 
                        2) AS persentase
                    FROM SLA_HMS
                    WHERE 1=1 {branch_filter}
                    GROUP BY Nama_Cabang, Status_ACCU
                """,
                'ban': f"""
                    SELECT 
                        Nama_Cabang,
                        Status_Ban,
                        ROUND(
                            (COUNT(*) * 1.0 / SUM(COUNT(*)) OVER (PARTITION BY Nama_Cabang)) * 100, 
                        2) AS persentase
                    FROM SLA_HMS
                    WHERE 1=1 {branch_filter}
                    GROUP BY Nama_Cabang, Status_Ban
                """,
                'kopling': f"""
                    SELECT 
                        Nama_Cabang,
                        Status_Kopling,
                        ROUND(
                            (COUNT(*) * 1.0 / SUM(COUNT(*)) OVER (PARTITION BY Nama_Cabang)) * 100, 
                        2) AS persentase
                    FROM SLA_HMS
                    WHERE tipe_transmisi <> 'A/T' {branch_filter}
                    GROUP BY Nama_Cabang, Status_Kopling
                """,
                'pb': f"""
                    SELECT 
                        Nama_Cabang,
                        Status_PB,
                        ROUND(
                            (COUNT(*) * 1.0 / SUM(COUNT(*)) OVER (PARTITION BY Nama_Cabang)) * 100, 
                        2) AS persentase
                    FROM SLA_HMS
                    WHERE 1=1 {branch_filter}
                    GROUP BY Nama_Cabang, Status_PB
                """
            }
            
            # Query detail
            query_detail = f"""
                SELECT
                Nomor_Customer,
                Nama_Customer,
                Nama_Cabang,
                Nomor_Equipment,
                Nomor_Polisi,
                Kelompok_Model,
                kategori_unit,
                Tipe_Transmisi,
                km_harian,
                Last_KM_Update,
                Last_KM_ACCU,
                Last_Tgl_Release_ACCU_SPK,
                Konsumsi_ACCU,
                Indikator_ACCU,
                Status_ACCU,
                Tgl_Plan_Pergantian_ACCU,
                Last_KM_Kopling,
                Last_Tgl_Release_Kopling_SPK,
                Konsumsi_Kopling,
                Indikator_Kopling,
                Status_Kopling,
                Tgl_Plan_Pergantian_Kopling,
                Last_KM_Ban,
                Last_Tgl_Release_Ban_SPK,
                Konsumsi_Ban,
                Indikator_Ban,
                Status_Ban,
                Last_KM_PB,
                Tgl_Last_Service_PB,
                Selisih_KM_Service,
                Status_PB,
                Next_Plan_KM_Service,
                Tanggal_Plan_Service
                FROM SLA_HMS
                WHERE 1=1 {branch_filter}
            """
            
            # Ambil data menggunakan cache
            results = self.fetch_or_get_cached_data(queries, branch_filter=branch_filter)
            branch_results = self.fetch_or_get_cached_data(branch_queries, is_branch_query=True, branch_filter=branch_filter)
            
            # Ambil data detail jika belum di-cache
            if f'data_detail_{branch_filter}' not in st.session_state.sla_data:
                st.session_state.sla_data[f'data_detail_{branch_filter}'] = self.db_connection.fetch_data(query_detail)
            data_detail = st.session_state.sla_data[f'data_detail_{branch_filter}']
                
            # Hitung persentase
            sla_percentages = {
                key: results[key]['persentase'].iloc[0] * 100 
                if results[key] is not None and not results[key].empty 
                else 0 
                for key in results
            }
            
            # Siapkan data cabang untuk grafik
            processed_branch_data = {}
            for key in branch_results:
                try:
                    processed_branch_data[key] = self.prepare_categorical_data(
                        branch_results[key], 
                        f'Status_{key.capitalize()}'
                    )
                except Exception as e:
                    st.error(f"Gagal memproses data untuk {key}: {e}")
                    processed_branch_data[key] = branch_results[key]
            
            # Buat gauge chart untuk SLA keseluruhan
            col3, col4, col5, col6 = st.columns(4)
            charts = [
                ('ACCU', sla_percentages['accu']),
                ('Kopling', sla_percentages['kopling']),
                ('PB', sla_percentages['pb']),
                ('Ban', sla_percentages['ban'])
            ]
            
            columns = [col3, col4, col5, col6]
            for (title, value), column in zip(charts, columns):
                with column:
                    st.plotly_chart(
                        self.create_gauge_chart(f"Persentase SLA {title}", value), 
                        use_container_width=True
                    )
            
            # Konfigurasi grafik batang
            bar_chart_configs = [
                ('accu', 'Persentase Capaian SLA ACCU by Cabang'),
                ('ban', 'Persentase Capaian SLA Ban by Cabang'),
                ('kopling', 'Persentase Capaian SLA Kopling by Cabang'),
                ('pb', 'Persentase Capaian SLA PB by Cabang')
            ]
            
            # Tata letak grafik batang
            col7, col8 = st.columns(2)
            col9, col10 = st.columns(2)
            
            chart_columns = [col7, col8, col9, col10]
            
            for (key, title), column in zip(bar_chart_configs, chart_columns):
                with column:
                    st.plotly_chart(
                        self.create_bar_chart(
                            processed_branch_data[key], 
                            title, 
                            f'Status_{key.capitalize()}'
                        ), 
                        use_container_width=True
                    )
            
            # Tampilkan data detail
            st.dataframe(data_detail)


    def main():
        """
        Fungsi utama untuk menginisialisasi dan menjalankan dashboard
        """
        # Konfigurasi database
        db_config = {
            'server': 'proddatapool.assa.id',
            'database': 'prod_fleet_dw',
            'username': 'fleetdw',
            'password': 'AssarentDW.2024',
            'driver': 'ODBC Driver 18 for SQL Server'
        }
        
        # Buat koneksi database
        db_connection = DatabaseConnection(**db_config)
        
        # Inisialisasi dan jalankan dashboard
        dashboard = SLADashboard(db_connection)
        dashboard.run_dashboard()

    # Pastikan skrip hanya dijalankan saat dieksekusi langsung
    if __name__ == "__main__":
        main()
