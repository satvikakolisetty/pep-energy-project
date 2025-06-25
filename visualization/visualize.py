import requests
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import os
from pathlib import Path

API_BASE_URL = "https://93xd2s2oef.execute-api.us-east-1.amazonaws.com/prod" 

# Set plotly to open visualizations in your default browser.
pio.renderers.default = "browser"

# Create a directory to save the charts
CHART_DIR = Path(__file__).parent / "charts"
CHART_DIR.mkdir(exist_ok=True)

# getting data
def fetch_data(endpoint):
    """function to fetch data from our API."""
    try:
        url = f"{API_BASE_URL}{endpoint}"
        print(f"Fetching data from: {url}")
        response = requests.get(url, timeout=30)
        response.raise_for_status()  # Raises an HTTPError for bad responses
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data from {endpoint}: {e}")
        return None

#Plotting Functions
def plot_anomaly_distribution(summary_data):
    """Creates a bar chart of anomaly distribution per site."""
    if not summary_data or 'site_anomaly_distribution' not in summary_data:
        print("No anomaly distribution data to plot.")
        return

    dist = summary_data['site_anomaly_distribution']
    if not dist:
        print("Anomaly distribution is empty.")
        return

    df = pd.DataFrame(list(dist.items()), columns=['Site ID', 'Anomaly Count'])
    df = df.sort_values(by='Anomaly Count', ascending=False)

    fig = go.Figure(data=[go.Bar(x=df['Site ID'], y=df['Anomaly Count'], marker_color='indianred')])
    fig.update_layout(
        title_text='Distribution of Anomalies Across Sites',
        xaxis_title='Site ID',
        yaxis_title='Number of Anomalies',
        template='plotly_white'
    )
    fig.write_html(CHART_DIR / "1_anomaly_distribution.html")
    print("Saved anomaly distribution chart to CHART_DIR/1_anomaly_distribution.html")


def plot_energy_trends(site_id, records):
    """Creates a line chart comparing energy generation and consumption for a site."""
    if not records:
        print(f"No records to plot for site {site_id}.")
        return

    df = pd.DataFrame(records)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.sort_values(by='timestamp')

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df['timestamp'], y=df['energy_generated_kwh'], mode='lines', name='Generated (kWh)', line=dict(color='green')))
    fig.add_trace(go.Scatter(x=df['timestamp'], y=df['energy_consumed_kwh'], mode='lines', name='Consumed (kWh)', line=dict(color='red')))
    
    fig.update_layout(title_text=f'Energy Trends for {site_id}', xaxis_title='Timestamp', yaxis_title='Energy (kWh)', template='plotly_white')
    
    file_name = CHART_DIR / f"2_energy_trends_{site_id}.html"
    fig.write_html(file_name)
    print(f"Saved energy trends chart to {file_name}")

def plot_net_energy_comparison(all_data):
    """Creates a bar chart comparing the total net energy (profitability) of each site."""
    net_energy_by_site = all_data.groupby('site_id')['net_energy_kwh'].sum().sort_values(ascending=False)
    
    fig = go.Figure(data=[go.Bar(x=net_energy_by_site.index, y=net_energy_by_site.values, marker_color='royalblue')])
    fig.update_layout(title_text='Net Energy Generation (Profitability) by Site', xaxis_title='Site ID', yaxis_title='Total Net Energy (kWh)', template='plotly_white')
    fig.write_html(CHART_DIR / "3_net_energy_comparison.html")
    print("Saved net energy comparison chart to CHART_DIR/3_net_energy_comparison.html")

def plot_site_efficiency(all_data):
    """Creates a bar chart comparing the efficiency of each site."""
    site_agg = all_data.groupby('site_id').agg(
        total_generated=('energy_generated_kwh', 'sum'),
        total_consumed=('energy_consumed_kwh', 'sum')
    ).reset_index()
    
    # Calculate efficiency score. Avoid division by zero.
    site_agg['efficiency'] = (1 - (site_agg['total_consumed'] / site_agg['total_generated'])) * 100
    site_agg = site_agg.sort_values(by='efficiency', ascending=False)

    fig = go.Figure(data=[go.Bar(x=site_agg['site_id'], y=site_agg['efficiency'], marker_color='purple')])
    fig.update_layout(title_text='Site Efficiency (Energy Retained)', xaxis_title='Site ID', yaxis_title='Efficiency Score (%)', template='plotly_white')
    fig.write_html(CHART_DIR / "4_site_efficiency.html")
    print("Saved site efficiency chart to CHART_DIR/4_site_efficiency.html")

def main():
    """Main function to run the visualization script."""

    # 1. Fetch summary data to get a list of all sites.
    print("\n<-----Fetching System Summary----->")
    summary_data = fetch_data("/summary")
    if not summary_data:
        print("Could not fetch summary data. Exiting.")
        return
        
    all_site_ids = summary_data.get('all_site_ids', [])
    if not all_site_ids:
        print("No site IDs found in summary data. Exiting.")
        return
    
    # 2. Plot the initial anomaly distribution chart.
    plot_anomaly_distribution(summary_data)
    
    # 3. Fetch detailed records for ALL sites to perform deeper analysis.
    print(f"\n--- Fetching detailed records for all {len(all_site_ids)} sites ---")
    all_records = []
    for site_id in all_site_ids:
        records_data = fetch_data(f"/records/{site_id}")
        if records_data:
            # Generate the individual trend chart for this site.
            plot_energy_trends(site_id, records_data)
            all_records.extend(records_data)
    
    # 4. Perform and plot the more advanced analyses using the complete dataset.
    if all_records:
        print("\n--- Performing Deeper Analysis on Full Dataset ---")
        full_df = pd.DataFrame(all_records)
        
        # Convert numeric columns properly, handling potential non-numeric data
        for col in ['energy_generated_kwh', 'energy_consumed_kwh', 'net_energy_kwh']:
            full_df[col] = pd.to_numeric(full_df[col], errors='coerce')
        
        plot_net_energy_comparison(full_df)
        plot_site_efficiency(full_df)
    else:
        print("No records found to perform detailed analysis.")

if __name__ == "__main__":
    main()
