import streamlit as st
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- 1. KONFIGURATION & DATEN ---
st.set_page_config(page_title="Trägerbemessungstool", layout="wide")

# Standard IPE Profile Daten (Bezeichnung, Masse [kg/m], Wy [cm^3])
IPE_DATA = {
    "IPE 80":  {"mass": 6.0,  "Wy": 20.0},
    "IPE 100": {"mass": 8.1,  "Wy": 34.2},
    "IPE 120": {"mass": 10.4, "Wy": 53.0},
    "IPE 140": {"mass": 12.9, "Wy": 77.3},
    "IPE 160": {"mass": 15.8, "Wy": 109.0},
    "IPE 180": {"mass": 18.8, "Wy": 146.0},
    "IPE 200": {"mass": 22.4, "Wy": 194.0},
    "IPE 220": {"mass": 26.2, "Wy": 252.0},
    "IPE 240": {"mass": 30.7, "Wy": 324.0},
    "IPE 270": {"mass": 36.1, "Wy": 429.0},
    "IPE 300": {"mass": 42.2, "Wy": 557.0},
    "IPE 330": {"mass": 49.1, "Wy": 713.0},
    "IPE 360": {"mass": 57.1, "Wy": 904.0},
    "IPE 400": {"mass": 66.3, "Wy": 1160.0},
    "IPE 450": {"mass": 77.6, "Wy": 1500.0},
    "IPE 500": {"mass": 90.7, "Wy": 1930.0},
    "IPE 550": {"mass": 106.0, "Wy": 2440.0},
    "IPE 600": {"mass": 122.0, "Wy": 3070.0},
}

STEEL_GRADES = {
    "S235": 235.0, # Streckgrenze in MPa (N/mm^2)
    "S355": 355.0
}

# --- 2. MECHANIK FUNKTIONEN ---

def calculate_distributed_moment_shear(L, q, x_vals):
    """Berechnet M und V für eine Gleichlast q (kN/m)."""
    Ra = q * L / 2
    V = Ra - q * x_vals
    M = (q * x_vals / 2) * (L - x_vals)
    return M, V

def calculate_triangular_moment_shear(L, q_max, x_vals):
    """Berechnet M und V für eine Dreieckslast."""
    Ra = (q_max * L) / 6
    V = Ra - (q_max * x_vals**2) / (2 * L)
    M = Ra * x_vals - (q_max * x_vals**3) / (6 * L)
    return M, V

def calculate_moving_load_envelope(L, Q, x_vals):
    """Simuliert die wandernde Last Q und gibt die Einhüllende zurück."""
    max_M = np.zeros_like(x_vals)
    max_V = np.zeros_like(x_vals)

    q_positions = np.linspace(0, L, int(L*10) + 1)

    for a in q_positions:
        Ra = Q * (L - a) / L
        
        V_temp = np.zeros_like(x_vals)
        M_temp = np.zeros_like(x_vals)
        
        mask_left = x_vals <= a
        mask_right = x_vals > a
        
        V_temp[mask_left] = Ra
        V_temp[mask_right] = Ra - Q 
        
        M_temp[mask_left] = Ra * x_vals[mask_left]
        M_temp[mask_right] = Ra * x_vals[mask_right] - Q * (x_vals[mask_right] - a)
        
        max_M = np.maximum(max_M, np.abs(M_temp))
        max_V = np.maximum(max_V, np.abs(V_temp))
        
    return max_M, max_V

# --- 3. UI LAYOUT ---

st.title("🏗️ Trägerbemessungstool (Bauinformatik WS 25/26)")
st.markdown("**Matrikelnummer:** 161486")

# Sidebar
st.sidebar.header("1. System & Lasten")
L = st.sidebar.number_input("Stützweite L [m]", value=5.86, step=0.1)
delta_g = st.sidebar.number_input("Ausbaulast Δg (Dreieckslast max) [kN/m]", value=16.0, step=0.5)
Q_load = st.sidebar.number_input("Verkehrslast Q (Wanderlast) [kN]", value=19.0, step=1.0)

st.sidebar.header("2. Material")
steel_grade = st.sidebar.selectbox("Stahlgüte", options=["S235", "S355"])
fy = STEEL_GRADES[steel_grade]

st.sidebar.markdown("---")
st.sidebar.markdown("**Teilsicherheitsbeiwerte:**")
gamma_G = 1.35
gamma_Q = 1.5
st.sidebar.latex(r"\gamma_G = 1.35, \quad \gamma_Q = 1.5")

# --- 4. BERECHNUNG & AUTO-DESIGN ---

st.header("2. Bemessungsergebnisse")
x = np.linspace(0, L, 200)

best_profile = None
results = {}

for profile_name, props in IPE_DATA.items():
    g_k = props["mass"] * 9.81 / 1000 
    
    # Schnittgrößen
    M_g, V_g = calculate_distributed_moment_shear(L, g_k, x)
    M_dg, V_dg = calculate_triangular_moment_shear(L, delta_g, x)
    M_Q, V_Q = calculate_moving_load_envelope(L, Q_load, x)
    
    # Superposition (Ed)
    M_Ed_array = 1.35 * (M_g + M_dg) + 1.5 * M_Q
    V_Ed_array = 1.35 * (np.abs(V_g) + np.abs(V_dg)) + 1.5 * V_Q
    
    max_M_Ed = np.max(M_Ed_array)
    max_V_Ed = np.max(V_Ed_array)
    
    # Nachweis
    sigma_Ed = (max_M_Ed / props["Wy"]) * 1000
    sigma_Rd = fy 
    utilization = sigma_Ed / sigma_Rd
    
    if utilization <= 1.0:
        best_profile = profile_name
        results = {
            "M_Ed": max_M_Ed,
            "V_Ed": max_V_Ed,
            "Sigma": sigma_Ed,
            "Util": utilization,
            "x": x,
            "M_array": M_Ed_array,
            "V_array": V_Ed_array
        }
        break

# --- 5. BERICHT & PLOTTING (INTERAKTIV) ---

if best_profile:
    col1, col2, col3 = st.columns(3)
    col1.metric("Gewähltes Profil", best_profile)
    col1.caption(f"Gewicht: {IPE_DATA[best_profile]['mass']} kg/m")
    
    col2.metric("Max. Bemessungsmoment (M_Ed)", f"{results['M_Ed']:.2f} kNm")
    col3.metric("Ausnutzungsgrad", f"{results['Util']*100:.1f}%")

    st.success(f"**Optimierung erfolgreich:** Das leichteste Profil ist **{best_profile}** mit einer Spannung von **{results['Sigma']:.1f} MPa**.")
    
    st.subheader("3. Interaktive Visualisierung")
    
    # Create interactive Plotly figure
    fig = make_subplots(rows=2, cols=1, 
                        shared_xaxes=True, 
                        vertical_spacing=0.1,
                        subplot_titles=("Biegemomentenlinie (M_Ed)", "Querkraftlinie (V_Ed)"))

    # Trace 1: Moment (Blue)
    fig.add_trace(go.Scatter(
        x=results['x'], 
        y=results['M_array'], 
        mode='lines', 
        name='M_Ed [kNm]',
        line=dict(color='blue', width=3),
        fill='tozeroy'
    ), row=1, col=1)

    # Trace 2: Shear (Red)
    fig.add_trace(go.Scatter(
        x=results['x'], 
        y=results['V_array'], 
        mode='lines', 
        name='V_Ed [kN]',
        line=dict(color='red', width=3),
        fill='tozeroy'
    ), row=2, col=1)

    # Layout Updates for Cursor and Styling
    fig.update_layout(
        height=700, 
        hovermode="x unified",  # This enables the 'Cursor' across both plots
        showlegend=True
    )

    fig.update_xaxes(title_text="Position x [m]", row=2, col=1)
    fig.update_yaxes(title_text="Moment [kNm]", row=1, col=1)
    fig.update_yaxes(title_text="Querkraft [kN]", row=2, col=1)

    # Render Plotly Chart in Streamlit
    st.plotly_chart(fig, use_container_width=True)

    # Details for Hand Calculation
    with st.expander("Berechnungsdetails anzeigen (Validierungshilfe)"):
        st.write("Werte für die Handrechnung:")
        st.latex(r"L = " + str(L) + r"\,m, \quad \Delta g = " + str(delta_g) + r"\,kN/m, \quad Q = " + str(Q_load) + r"\,kN")
        st.write(f"**Eigengewicht ($g$) von {best_profile}:** {IPE_DATA[best_profile]['mass'] * 9.81 / 1000:.4f} kN/m")
else:
    st.error("Kein Profil gefunden.")