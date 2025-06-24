import requests
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

# IMPORTANT: Replace this with the actual API endpoint URL you get from your
# Terraform output after deployment.
API_BASE_URL = "https://aigbzcfh87.execute-api.us-east-1.amazonaws.com/prod" 

# Set plotly to open charts in your default browser.
pio.renderers.default = "browser"

def fetch_data(endpoint):
    """Helper function to fetch data from our API."""
    try:
        url = f"{API_BASE_URL}{endpoint}"
        print(f"Fetching data from: {url}")
        response = requests.get(url)
        response.raise_for_status()  # Raises an HTTPError for bad responses
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data from {endpoint}: {e}")
        return None

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

    fig = go.Figure(data=[go.Bar(x=df['Site ID'], y=df['Anomaly Count'])])
    fig.update_layout(
        title_text='Distribution of Anomalies Across Sites',
        xaxis_title='Site ID',
        yaxis_title='Number of Anomalies',
        template='plotly_white'
    )
    fig.write_html("anomaly_distribution.html")
    print("Saved anomaly distribution chart to anomaly_distribution.html")


def plot_energy_trends(site_id, records):
    """Creates a line chart comparing energy generation and consumption for a site."""
    if not records:
        print(f"No records to plot for site {site_id}.")
        return

    df = pd.DataFrame(records)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.sort_values(by='timestamp')

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df['timestamp'],
        y=df['energy_generated_kwh'],
        mode='lines+markers',
        name='Energy Generated (kWh)',
        line=dict(color='green')
    ))

    fig.add_trace(go.Scatter(
        x=df['timestamp'],
        y=df['energy_consumed_kwh'],
        mode='lines+markers',
        name='Energy Consumed (kWh)',
        line=dict(color='red')
    ))

    fig.update_layout(
        title_text=f'Energy Trends for {site_id}',
        xaxis_title='Timestamp',
        yaxis_title='Energy (kWh)',
        template='plotly_white',
        legend_title_text='Metric'
    )
    
    file_name = f"energy_trends_{site_id}.html"
    fig.write_html(file_name)
    print(f"Saved energy trends chart to {file_name}")


def main():

    # 1. Fetch summary data and plot anomaly distribution.
    print("\n--- Fetching System Summary ---")
    summary_data = fetch_data("/summary")
    if summary_data:
        plot_anomaly_distribution(summary_data)
        
        # Get a list of unique site IDs from the summary data
        site_ids = list(summary_data.get('site_anomaly_distribution', {}).keys())
        if not site_ids:
             # Fallback if no anomalies, try to get sites from a sample of records
             print("No sites with anomalies found, fetching a sample record to get a site ID...")
             sample_records = fetch_data("/records/site-alpha-pv-farm-01") # a default site
             if sample_records:
                 site_ids = [sample_records[0]['site_id']]


        # 2. For the first site in the list, fetch its detailed records and plot its trends.
        if site_ids:
            first_site = site_ids[0]
            print(f"\n--- Fetching Detailed Records for Site: {first_site} ---")
            records_data = fetch_data(f"/records/{first_site}")
            if records_data:
                plot_energy_trends(first_site, records_data)
        else:
            print("Could not determine any site IDs to fetch detailed data.")

if __name__ == "__main__":
    main()
