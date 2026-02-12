# dashboard/app.py
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import sys
from pathlib import Path
from datetime import datetime

project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from src.utils.helpers import load_config
from src.alert_system.alert_manager import AlertStorage 

# page config
st.set_page_config(
    page_title="Disaster alert system",
    layout="wide",
    initial_sidebar_state="expanded"
)

# custom CSS (consolidated redundant classes)
st.markdown("""
    <style>
    .main { padding: 0rem 1rem; }
    .stMetric { background-color: #f0f2f6; padding: 15px; border-radius: 5px; }
    .alert-card { padding: 15px; border-radius: 5px; margin: 10px 0; color: white; }
    .alert-severe { background-color: #dc3545; }
    .alert-high { background-color: #fd7e14; }
    .alert-moderate { background-color: #ffc107; color: black; }
    .alert-low { background-color: #17a2b8; }
    </style>
    """, unsafe_allow_html=True)

# initialize session state
if 'last_refresh' not in st.session_state:
    st.session_state.last_refresh = datetime.now()

# load config
@st.cache_resource
def get_config():
    return load_config()

config = get_config()

# initialize components
@st.cache_resource
def get_alert_storage():
    return AlertStorage()

alert_storage = get_alert_storage()

# sidebar
with st.sidebar:
    st.image("https://via.placeholder.com/200x100/007bff/ffffff?text=ALERT+SYSTEM", 
             use_container_width=True)
    st.title("Disaster alert system")
    st.markdown("---")
    
    # navigation
    page = st.radio(
        "Navigation",
        ["Dashboard", "Active alerts", "Analytics", "About"]  # Settings removed - non-functional
    )
    
    st.markdown("---")
    
    # auto-refresh
    auto_refresh = st.checkbox("Auto-refresh (60s)", value=False)
    
    if st.button("🔄 Refresh now") or auto_refresh:
        st.session_state.last_refresh = datetime.now()
        st.rerun()
    
    st.markdown("---")
    
    # system status
    st.subheader("System status")
    st.success("System online")
    st.info(f"Last updated: {st.session_state.last_refresh.strftime('%H:%M:%S')}")

# helper functions
def get_alert_color(level_name):
    """Get color for alert level"""
    colors = {
        'SEVERE': '#dc3545',
        'HIGH': '#fd7e14',
        'MODERATE': '#ffc107',
        'LOW': '#17a2b8'
    }
    return colors.get(level_name, '#6c757d')

def display_alert_card(alert_dict):
    """Display an alert as a card"""
    level = alert_dict['level']
    color_class = f"alert-{level.lower()}"
    
    st.markdown(f"""
        <div class="alert-card {color_class}">
            <h4 style="margin: 0;">{level} - {alert_dict['hazard_type'].upper()}</h4>
            <p style="margin: 5px 0;"><strong>Location:</strong> {alert_dict['location']}</p>
            <p style="margin: 5px 0;"><strong>Probability:</strong> {alert_dict['probability']:.1%}</p>
            <p style="margin: 5px 0;"><strong>Time:</strong> {alert_dict['timestamp']}</p>
            <p style="margin: 10px 0 0 0; font-size: 14px;">{alert_dict['message']}</p>
        </div>
    """, unsafe_allow_html=True)

# page 1
if page == "Dashboard":
    st.title("Dashboard overview")
    
    # get active alerts
    active_alerts = alert_storage.get_active_alerts()
    
    # top metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_alerts = len(active_alerts)
        st.metric("Active alerts", total_alerts)
    
    with col2:
        severe_count = len([a for a in active_alerts if a['level_value'] >= 4])
        st.metric("Severe/Critical", severe_count)
    
    with col3:
        eq_count = len([a for a in active_alerts if a['hazard_type'] == 'earthquake'])
        st.metric("Earthquake alerts", eq_count)
    
    with col4:
        flood_count = len([a for a in active_alerts if a['hazard_type'] == 'flood'])
        st.metric("Flood alerts", flood_count)
    
    st.markdown("---")
    
    # alert map (with dummy coordinates for demo)
    st.subheader("Alert locations")
    
    if active_alerts:
        map_data = []
        for alert in active_alerts:
            map_data.append({
                'location': alert['location'],
                'level': alert['level'],
                'hazard_type': alert['hazard_type'],
                'probability': alert['probability'],
                'lat': np.random.uniform(37.33, 37.35),
                'lon': np.random.uniform(-121.90, -121.87)
            })
        
        df_map = pd.DataFrame(map_data)
        fig = px.scatter_mapbox(
            df_map,
            lat='lat',
            lon='lon',
            color='level',
            size='probability',
            hover_name='location',
            hover_data=['hazard_type', 'probability'],
            color_discrete_map={
                'SEVERE': '#dc3545',
                'HIGH': '#fd7e14',
                'MODERATE': '#ffc107',
                'LOW': '#17a2b8'
            },
            zoom=5,
            height=500
        )
        fig.update_layout(mapbox_style="open-street-map")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No active alerts to display on map")
    
    st.markdown("---")
    
    # recent alerts timeline
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Recent alerts")
        
        if active_alerts:
            sorted_alerts = sorted(active_alerts, 
                                  key=lambda x: x['timestamp'], 
                                  reverse=True)
            
            for alert in sorted_alerts[:5]:
                display_alert_card(alert)
        else:
            st.info("No active alerts")
    
    with col2:
        st.subheader("Alert trends (7 Days)")
        
        history_df = alert_storage.get_alert_history(days=7)
        
        if not history_df.empty:
            history_df['date'] = pd.to_datetime(history_df['timestamp']).dt.date
            daily_counts = history_df.groupby(['date', 'hazard_type']).size().reset_index(name='count')
            
            fig = px.bar(
                daily_counts,
                x='date',
                y='count',
                color='hazard_type',
                title='Alerts per day',
                color_discrete_map={
                    'earthquake': '#ff6b6b',
                    'flood': '#4ecdc4'
                }
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No historical data available")

# page 2
elif page == "Active alerts":
    st.title("Active alerts")
    
    # filters
    col1, col2, col3 = st.columns(3)
    
    with col1:
        hazard_filter = st.selectbox(
            "Hazard type",
            ["All", "Earthquake", "Flood"]
        )
    
    with col2:
        level_filter = st.selectbox(
            "Alert level",
            ["All", "SEVERE", "HIGH", "MODERATE", "LOW"]
        )
    
    with col3:
        sort_by = st.selectbox(
            "Sort By",
            ["Time (Newest)", "Time (Oldest)", "Probability (High)", "Level (High)"]
        )
    
    # get alerts
    active_alerts = alert_storage.get_active_alerts()
    
    # apply filters
    filtered_alerts = active_alerts
    
    if hazard_filter != "All":
        filtered_alerts = [a for a in filtered_alerts 
                          if a['hazard_type'] == hazard_filter.lower()]
    
    if level_filter != "All":
        filtered_alerts = [a for a in filtered_alerts 
                          if a['level'] == level_filter]
    
    # sort
    if sort_by == "Time (Newest)":
        filtered_alerts = sorted(filtered_alerts, 
                                key=lambda x: x['timestamp'], 
                                reverse=True)
    elif sort_by == "Time (Oldest)":
        filtered_alerts = sorted(filtered_alerts, 
                                key=lambda x: x['timestamp'])
    elif sort_by == "Probability (High)":
        filtered_alerts = sorted(filtered_alerts, 
                                key=lambda x: x['probability'], 
                                reverse=True)
    elif sort_by == "Level (High)":
        filtered_alerts = sorted(filtered_alerts, 
                                key=lambda x: x['level_value'], 
                                reverse=True)
    
    # display alerts
    st.markdown(f"### Showing {len(filtered_alerts)} alerts")
    
    if filtered_alerts:
        for alert in filtered_alerts:
            with st.expander(
                f"{alert['level']} - {alert['hazard_type'].upper()} - {alert['location']}", 
                expanded=False
            ):
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    st.markdown(f"**Message:** {alert['message']}")
                    st.markdown(f"**Probability:** {alert['probability']:.1%}")
                    st.markdown(f"**Time:** {alert['timestamp']}")
                
                with col2:
                    if 'metadata' in alert and alert['metadata']:
                        st.markdown("**Additional info:**")
                        for key, value in alert['metadata'].items():
                            st.markdown(f"- {key}: {value}")
    else:
        st.info("No alerts match the selected filters")

# page 3
elif page == "Analytics":
    st.title("Analytics & statistics")
    
    # time range selector
    days_range = st.slider("Time range (days)", 1, 90, 30)
    
    # get historical data
    history_df = alert_storage.get_alert_history(days=days_range)
    
    if history_df.empty:
        st.warning("No data available for the selected time range")
    else:
        st.success(f"Found {len(history_df)} alerts in the last {days_range} days")
        
        # statistics cards
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total alerts", len(history_df))
        
        with col2:
            st.metric("Avg probability", f"{history_df['probability'].mean():.1%}")
        
        with col3:
            severe_count = len(history_df[history_df['level_value'] >= 4])
            st.metric("Severe/Critical", severe_count)
        
        with col4:
            st.metric("Unique locations", history_df['location'].nunique())
        
        st.markdown("---")
        
        # charts
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Alerts by hazard type")
            
            hazard_counts = history_df['hazard_type'].value_counts()
            
            fig = px.pie(
                values=hazard_counts.values,
                names=hazard_counts.index,
                title='Distribution by hazard type',
                color_discrete_map={
                    'earthquake': '#ff6b6b',
                    'flood': '#4ecdc4'
                }
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.subheader("Alerts by level")
            
            level_counts = history_df['level'].value_counts()
            
            fig = px.bar(
                x=level_counts.index,
                y=level_counts.values,
                title='Distribution by alert level',
                labels={'x': 'Alert level', 'y': 'Count'},
                color=level_counts.index,
                color_discrete_map={
                    'SEVERE': '#dc3545',
                    'HIGH': '#fd7e14',
                    'MODERATE': '#ffc107',
                    'LOW': '#17a2b8'
                }
            )
            st.plotly_chart(fig, use_container_width=True)
        
        st.markdown("---")
        
        # time series
        st.subheader("Alert frequency over time")
        
        history_df['date'] = pd.to_datetime(history_df['timestamp']).dt.date
        daily_counts = history_df.groupby(['date', 'hazard_type']).size().reset_index(name='count')
        
        fig = px.line(
            daily_counts,
            x='date',
            y='count',
            color='hazard_type',
            title='Daily alert count',
            color_discrete_map={
                'earthquake': '#ff6b6b',
                'flood': '#4ecdc4'
            }
        )
        st.plotly_chart(fig, use_container_width=True)
        
        st.markdown("---")
        
        # raw data table
        with st.expander("View raw data"):
            st.dataframe(
                history_df[['timestamp', 'hazard_type', 'level', 'location', 'probability']]
                .sort_values('timestamp', ascending=False),
                use_container_width=True
            )
            
            # download button
            csv = history_df.to_csv(index=False)
            st.download_button(
                label="📥 Download CSV",
                data=csv,
                file_name=f'alert_history_{datetime.now().strftime("%Y%m%d")}.csv',
                mime='text/csv'
            )

# page 4
elif page == "About":
    st.title("About this system")
    
    st.markdown("""
    ## Earthquake & Flood Early Warning System
    
    ### Overview
    This system provides real-time monitoring and early warning for earthquakes and floods
    using machine learning models trained on historical USGS data.
    
    ### Features
    - **Real-time monitoring**: Continuous monitoring of seismic activity and river levels
    - **AI predictions**: Machine learning models predict potential disasters
    - **Multi-level alerts**: LOW, MODERATE, HIGH, and SEVERE alert levels
    - **Notifications**: Email and logging notifications
    - **Analytics**: Historical data analysis and trends
    
    ### Data sources
    - **Earthquakes**: [USGS Earthquake Catalog](https://earthquake.usgs.gov/)
    - **Floods**: [USGS Water Data](https://waterdata.usgs.gov/)
    
    ### Alert levels
    
    | Level | Probability range | Description |
    |-------|------------------|-------------|
    | LOW | 30-50% | Monitor conditions |
    | MODERATE | 50-70% | Stay informed |
    | HIGH | 70-90% | Prepare for action |
    | SEVERE | 90%+ | Take immediate action |
    
    ### Monitoring sites
    """)
    
    # display monitoring sites
    st.markdown("#### Flood monitoring sites")
    sites_df = pd.DataFrame([
        {'Site ID': site_id, 'Location': site_name}
        for site_id, site_name in config['flood']['monitoring_sites'].items()
    ])
    st.dataframe(sites_df, use_container_width=True)
    
    st.markdown("---")
    
    st.markdown("""
    ### Disclaimer
    
    This system is intended to provide early warning and assist with disaster preparedness.
    It should not be used as the sole basis for emergency decisions. Always follow
    official government alerts and emergency management guidance.
    """)

# footer
st.markdown("---")
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("**Earthquake & Flood Alert System**")

with col2:
    st.markdown(f"Last refresh: {st.session_state.last_refresh.strftime('%Y-%m-%d %H:%M:%S')}")

with col3:
    st.markdown("Data source: [USGS](https://www.usgs.gov/)")