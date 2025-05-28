import os
import uuid
import pandas as pd
from flask import Flask, render_template, request, send_file, session, redirect, url_for
import xlwt

app = Flask(__name__)
app.secret_key = 'clave-secreta-para-session'

CAMPAÑAS = [
    "BFBDELT1", "BFBT0A", "BFBT1A", "BFBT2A", "BFBT3A", "CNCBLOQ1",
    "CNCCAST1", "CNCT0", "CNCT1", "CRLEGAL", "FOHCASTI", "FOHT1A",
    "FOHVENC3", "GNBCAST1", "GNBVENC1", "IBK01", "IBK03", "IBK04", "IBK08",
    "IBKCAST1", "IBKT1A", "MAFCAST", "MAFJNR1", "MAFT2T3", "SANT1", "SANT2"
]

TEMP_FOLDER = 'temp'
TELEFONOS_FILE = 'telefonos.csv'

if not os.path.exists(TEMP_FOLDER):
    os.makedirs(TEMP_FOLDER)

def obtener_telefonos_por_campania(campania):
    df_tels = pd.read_csv(TELEFONOS_FILE)
    fila = df_tels[df_tels['campania'].str.upper() == campania.upper()]
    if fila.empty:
        return None
    return (
        fila.iloc[0]['phone_number_default'],
        fila.iloc[0]['phone_number_super'],
        fila.iloc[0]['phone_number_jefe']
    )

def guardar_xls(df, ruta):
    wb = xlwt.Workbook()
    ws = wb.add_sheet('Sheet1')
    style_yellow = xlwt.easyxf('pattern: pattern solid, fore_colour yellow;')

    for col_num, col_name in enumerate(df.columns):
        ws.write(0, col_num, col_name)

    for row_num, row in enumerate(df.itertuples(index=False), start=1):
        for col_num, value in enumerate(row):
            if (row_num <= 3) or (row_num > len(df) - 3):
                ws.write(row_num, col_num, value, style_yellow)
            else:
                ws.write(row_num, col_num, value)

    wb.save(ruta)

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        modulo = request.form.get('modulo')
        archivos = request.files.getlist('archivos')

        if modulo not in ['audio', 'mudo']:
            return "Módulo inválido", 400
        if not archivos or len(archivos) == 0:
            return "No se subió ningún archivo", 400

        resultados = []

        for archivo in archivos:
            nombre_archivo = archivo.filename
            campaña_detectada = next((c for c in CAMPAÑAS if c in nombre_archivo.upper()), None)

            if not campaña_detectada:
                resultados.append({
                    'nombre_archivo': nombre_archivo,
                    'error': "No se pudo detectar campaña en el nombre del archivo."
                })
                continue

            try:
                df = pd.read_excel(archivo)
                df.iloc[:, 0] = df.iloc[:, 0].astype(str)
                df.iloc[:, 1] = df.iloc[:, 1].astype(str)
                df['city'] = campaña_detectada
                df['state'] = 1 if modulo == 'audio' else 0

                cantidad_ingresada = len(df)
                uid = str(uuid.uuid4())
                nombre_temp = f"{uid}_procesado.xls"
                ruta_temp = os.path.join(TEMP_FOLDER, nombre_temp)

                if modulo == 'audio':
                    telefonos = obtener_telefonos_por_campania(campaña_detectada)
                    if not telefonos:
                        resultados.append({
                            'nombre_archivo': nombre_archivo,
                            'error': f"No se encontraron teléfonos para la campaña {campaña_detectada}"
                        })
                        continue

                    tel_default, tel_super, tel_jefe = telefonos
                    filas_insertar = pd.DataFrame([
                        ["11111111", str(tel_default), campaña_detectada, 1],
                        ["11111111", str(tel_super), campaña_detectada, 1],
                        ["11111111", str(tel_jefe), campaña_detectada, 1]
                    ], columns=df.columns)

                    df_final = pd.concat([filas_insertar, df, filas_insertar], ignore_index=True)
                else:
                    df_final = df

                guardar_xls(df_final, ruta_temp)
                cantidad_final = len(df_final)

                resultados.append({
                    'nombre_archivo': nombre_archivo,
                    'archivo_temp': nombre_temp,
                    'campaña': campaña_detectada,
                    'cantidad_ingresada': cantidad_ingresada,
                    'cantidad_final': cantidad_final
                })

            except Exception as e:
                resultados.append({
                    'nombre_archivo': nombre_archivo,
                    'error': f"Error procesando archivo: {e}"
                })

        session['resultados'] = resultados
        return render_template('indexGlobal.html', resultados=resultados, modulo=modulo)

    return render_template('indexGlobal.html')

@app.route('/descargar_multiple')
def descargar_multiple():
    archivo_temp = request.args.get('archivo')
    nombre_original = request.args.get('nombre')

    if not archivo_temp or not nombre_original:
        return redirect(url_for('index'))

    ruta_temp = os.path.join(TEMP_FOLDER, archivo_temp)
    if not os.path.exists(ruta_temp):
        return "Archivo temporal no encontrado.", 404

    respuesta = send_file(
        ruta_temp,
        as_attachment=True,
        download_name=os.path.splitext(nombre_original)[0] + ".xls",
        mimetype='application/vnd.ms-excel'
    )

    @respuesta.call_on_close
    def cleanup():
        try:
            os.remove(ruta_temp)
        except Exception as e:
            print(f"Error eliminando archivo temporal: {e}")

    return respuesta

if __name__ == '__main__':
    app.run(debug=True)
