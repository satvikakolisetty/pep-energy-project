import os
import json
import random
import boto3
import datetime

# Fetch the S3 bucket name from the output env variables configured in Terraform.
S3_BUCKET_NAME = os.environ['S3_BUCKET_NAME']

# Initialize the S3 client
s3_client = boto3.client('s3')

# mock energy sites.
SITES = [
    "site-alpha-pv-farm-01",
    "site-beta-wind-turbine-03",
    "site-gamma-hydro-plant-01",
    "site-delta-solar-roof-02",
    "site-epsilon-geothermal-01"
]

def generate_data_handler(event, context):
    """
    This Lambda function generates mock energy data for multiple sites
    and uploads it to a specified S3 bucket.
    It will be triggered by an EventBridge schedule that is for every 5 mi.
    """
    print(f"Generating data for {len(SITES)} sites..")
    
    all_records = []
    

    # Loop through each site and generate a small batch of data records.
    for site_id in SITES:
        # random number of readings (5-15) for each site
        num_records_for_site = random.randint(5, 15)
        
        # Start with the current time and step backwards for each record.
        timestamp = datetime.datetime.utcnow()
        # Introducing a 10% chance of generating an anomalous record for testing purpose.
        is_anomaly = random.random() < 0.1
        for i in range(num_records_for_site):
        
            if is_anomaly:
                if random.choice([True, False]):
                    # If it's an anomaly, randomly pick a condition to violate to test both specified anomaly cases.
                    # energy_generated_kwh < 0
                    energy_generated = -1 * random.uniform(10.0, 50.0)
                    energy_consumed = random.uniform(20.0, 80.0)
                else:
                    # energy_consumed_kwh < 0
                    energy_generated = random.uniform(50.0, 500.0)
                    energy_consumed = -1 * random.uniform(10.0, 50.0)

            else:
                # Generate normal data.
                energy_generated = random.uniform(50.0, 500.0)
                # Consumption is always less than generation
                energy_consumed = random.uniform(10.0, energy_generated * 0.8)

            # Each record in the batch gets a slight earlier timestamp.
            record_timestamp = timestamp - datetime.timedelta(seconds=i * 15)

            record = {
                'site_id': site_id,
                'timestamp': record_timestamp.isoformat() + "Z", 
                'energy_generated_kwh': round(energy_generated, 2),
                'energy_consumed_kwh': round(energy_consumed, 2)
            }
            all_records.append(record)

    # Create a unique filename based on the current timestamp.
    file_timestamp = datetime.datetime.utcnow().strftime('%Y-%m-%d-%H-%M-%S')
    file_name = f"raw/energy_data_{file_timestamp}.json"
    
    print(f"Uploading {len(all_records)} total records to {S3_BUCKET_NAME}/{file_name}")

    # The function will fail if it can't upload the file
    try:
        s3_client.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=file_name,
            Body=json.dumps(all_records, indent=2),
            ContentType='application/json'
        )
        print("Upload successful.")
        return {
            'statusCode': 200,
            'body': json.dumps(f'Successfully uploaded {file_name} to {S3_BUCKET_NAME}')
        }
    except Exception as e:
        print(f"Error uploading file to S3: {str(e)}")
        raise e