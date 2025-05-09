import numpy as np
import pandas as pd
import sklearn
import matplotlib.pyplot as plt
from rdkit import Chem
from rdkit.Chem import AllChem
from rdkit.Chem import Descriptors
from rdkit.ML.Descriptors import MoleculeDescriptors
from sklearn import datasets
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error, r2_score
import seaborn as sns
import statsmodels.api as sm
import warnings
import py3Dmol
from itertools import combinations
from sklearn.preprocessing import StandardScaler
from sklearn.preprocessing import MinMaxScaler
import itertools
import itables
itables.init_notebook_mode()

warnings.filterwarnings('ignore')


def graficar_heatmap_pearson(df, columna_inicio, titulo='Heatmap de correlaciones de Pearson', figsize=(14,11)):
    """
    Genera un heatmap de correlaciones de Pearson absolutas desde una columna en adelante.

    Parámetros:
        df (pd.DataFrame): DataFrame con los datos.
        columna_inicio (str): Nombre de la primera columna a incluir.
        titulo (str): Título del gráfico.
        figsize (tuple): Tamaño del gráfico.
    """
    # Obtener todas las columnas a partir de columna_inicio
    idx_inicio = df.columns.get_loc(columna_inicio)
    columnas = df.columns[idx_inicio:]

    # Calcular la matriz de correlación absoluta
    matriz_corr = df[columnas].corr(method='pearson', numeric_only=True).abs()

    # Crear y mostrar heatmap
    fig, ax = plt.subplots(figsize=figsize)
    sns.heatmap(matriz_corr, annot=True).set(title=titulo)
    ax.xaxis.tick_top()
    plt.xticks(rotation=90)
    plt.show()


def analizar_regresiones_lineales_simples(df, variable_objetivo, columnas_descriptores, graficar=True):
    """
    Realiza regresiones lineales simples entre una variable objetivo y una lista de descriptores.
    
    Parámetros:
        df (pd.DataFrame): Conjunto de datos.
        variable_objetivo (str): Nombre de la columna dependiente (e.g., 'IC50_value_B2_scaled').
        columnas_descriptores (list): Lista de nombres de las columnas independientes.
        graficar (bool): Si True, muestra el gráfico de regresión para cada descriptor.
    
    Retorna:
        DataFrame con Descriptor, R², Coeficiente e Intercepto ordenado por R² descendente.
    """
    resultados = []

    for var in columnas_descriptores:
        if graficar:
            plt.figure()
            sns.regplot(x=var, y=variable_objetivo, data=df).set(
                title=f'Regression plot of {var} vs {variable_objetivo}')
            plt.show()
        
        X = df[[var]]
        y = df[[variable_objetivo]]
        
        regressor = LinearRegression()
        regressor.fit(X, y)
        y_pred = regressor.predict(X)
        
        X2 = sm.add_constant(X)
        est = sm.OLS(y, X2).fit()
        
        # Extraer coeficiente y error estándar (índice 1 es la variable, 0 sería la constante)
        coef = est.params[1]
        std_err = est.bse[1]
        intercepto = est.params[0]
                
        print(est.summary())
        print('R\u00b2: %.3f' % est.rsquared)
        print('-' * 80)
        
        resultados.append([var, est.rsquared, coef, std_err, intercepto])

    df_resultados = pd.DataFrame(resultados, columns=['Descriptor', 'R²', 'Coeficiente', 'Std err', 'Intercepto'])
    return df_resultados.sort_values(by='R²', ascending=False)



def correlaciones_validas(subset, pearsoncorr, umbral=0.6):
    for var1, var2 in itertools.combinations(subset, 2):
        if abs(pearsoncorr.loc[var1, var2]) >= umbral:
            return False
    return True

def obtener_combinaciones_validas(df, columnas, umbral=0.6):
    """
    Devuelve una lista de combinaciones de variables que cumplen con el umbral de correlación.

    Parámetros:
        df (DataFrame): DataFrame con los datos.
        columnas (list): Lista de nombres de columnas/descriptores.
        umbral (float): Umbral de correlación para considerar combinaciones como válidas.

    Retorna:
        Lista de tuplas con combinaciones válidas.
    """
    # Calculamos la matriz de correlación una sola vez
    pearsoncorr = df[columnas].corr(method='pearson', numeric_only=True)
    pearsoncorrpost = pearsoncorr.apply(abs)

    combinaciones_validas = []
    
    for r in range(1, len(columnas)+1):
        for subset in itertools.combinations(columnas, r):
            if correlaciones_validas(subset, pearsoncorrpost):
                combinaciones_validas.append(subset)
    
    return combinaciones_validas

def evaluar_modelos_qsar(df, descriptores, y_col='IC50_value_nM_norm'):
    """
    Evalúa modelos de regresión lineal múltiple para combinaciones válidas de variables según un umbral de correlación.

    Parámetros:
        df (DataFrame): DataFrame con los datos.
        descriptores (list): Lista de nombres de columnas a considerar como descriptores.
        y_col (str): Nombre de la columna objetivo.

    Devuelve:
        DataFrame con resultados ordenados por R².
    """
    combis_validas = obtener_combinaciones_validas(df, descriptores)

    resultados = []

    for subset in combis_validas:
        X = df[list(subset)]
        X = sm.add_constant(X)
        y = df[y_col]

        model = sm.OLS(y, X).fit()

        resultados.append({
            "Variables": list(subset),
            "R2": round(model.rsquared, 3),
            "Coeficientes": [round(c, 4) for c in model.params[1:]],  # sin constante
            "Errores_Estandar": [round(se, 4) for se in model.bse[1:]],
            "Intercepto": round(model.params[0], 4),
            "Cantidad_de_variables": len(subset)
        })

    resultados_df = pd.DataFrame(resultados)
    resultados_final = resultados_df.sort_values(by="R2", ascending=False)
    return resultados_final

# Lista completa de descriptores disponibles
descList = Descriptors.descList

def calcular_descriptores_molecula(mol, seleccion=None):
    """
    Calcula descriptores de una molécula usando RDKit.

    Parámetros:
        mol (Mol): Molécula RDKit.
        seleccion (list, opcional): Lista de nombres de descriptores a calcular. Si es None, calcula todos.

    Retorna:
        dict: Diccionario con nombre y valor de cada descriptor.
    """
    resultados = {}
    for nombre, func in descList:
        if (seleccion is None) or (nombre in seleccion):
            try:
                resultados[nombre] = func(mol)
            except Exception:
                resultados[nombre] = None
    return resultados

def agregar_descriptores(df, smiles_col='canonical_smiles', seleccion=None, antes_de_columna=None):
    """
    Agrega descriptores RDKit al DataFrame y los ubica antes de una columna específica si se indica.

    Parámetros:
        df (DataFrame): Debe contener una columna con SMILES.
        smiles_col (str): Nombre de la columna con SMILES.
        seleccion (list, opcional): Lista de nombres de descriptores a agregar.
        antes_de_columna (str, opcional): Nombre de la columna antes de la cual insertar los descriptores.

    Retorna:
        DataFrame con columnas reordenadas.
    """
    resultados = []
    for smi in df[smiles_col]:
        mol = Chem.MolFromSmiles(smi)
        if mol:
            resultados.append(calcular_descriptores_molecula(mol, seleccion=seleccion))
        else:
            resultados.append({nombre: None for nombre, _ in descList if (seleccion is None or nombre in seleccion)})
    
    df_descriptores = pd.DataFrame(resultados)

    df = df.reset_index(drop=True)
    df_descriptores = df_descriptores.reset_index(drop=True)
    df_final = pd.concat([df, df_descriptores], axis=1)

    # Si no se especifica columna de referencia, devolvemos tal cual
    if antes_de_columna is None or antes_de_columna not in df.columns:
        return df_final

    # Reordenamos columnas
    cols = df.columns.tolist()
    descriptores_cols = df_descriptores.columns.tolist()

    idx = cols.index(antes_de_columna)
    nuevas_orden = cols[:idx] + descriptores_cols + cols[idx:]
    
    # Evitamos duplicados (por si los descriptores están también al final)
    nuevas_orden = [col for col in nuevas_orden if col in df_final.columns]

    return df_final[nuevas_orden]

def normalizar_columnas_seleccionadas(df, columnas, metodo="minmax"):
    """
    Normaliza columnas numéricas especificadas.

    Parámetros:
        df (pd.DataFrame): DataFrame original.
        columnas (list): Lista de nombres de columnas a normalizar.
        metodo (str): "minmax" o "standard".

    Retorna:
        pd.DataFrame: DataFrame original + columnas normalizadas con sufijo "_norm".
    """
    datos = df[columnas]

    # Escalador elegido
    if metodo == "minmax":
        scaler = MinMaxScaler()
    elif metodo == "standard":
        scaler = StandardScaler()
    else:
        raise ValueError("El método debe ser 'minmax' o 'standard'.")

    # Normalización
    datos_escalados = scaler.fit_transform(datos)
    columnas_escaladas = [col + "_norm" for col in columnas]
    df_scaled = pd.DataFrame(datos_escalados, columns=columnas_escaladas, index=df.index)

    # Combinar con el DataFrame original
    return pd.concat([df, df_scaled], axis=1)
