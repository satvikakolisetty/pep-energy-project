import os
from typing import List, Optional, Dict
import boto3
from boto3.dynamodb.conditions import Key, Attr
from fastapi import FastAPI, HTTPException, Query, Path
from pydantic import BaseModel, Field
from decimal import Decimal
from collections import Counter

#Configuration and Initialization
DYNAMODB_TABLE_NAME = os.environ['DYNAMODB_TABLE_NAME']
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(DYNAMODB_TABLE_NAME)

# Pydantic Models for Data Validation
# This model defines the structure of the data we'll return.
# FastAPI uses this for response validation.
class EnergyRecord(BaseModel):
    site_id: str = Field(..., description="Unique identifier for the energy site.")
    timestamp: str = Field(..., description="UTC timestamp of the record.")
    energy_generated_kwh: float = Field(..., description="Energy generated in kWh.")
    energy_consumed_kwh: float = Field(..., description="Energy consumed in kWh.")
    net_energy_kwh: float = Field(..., description="Net energy (generated - consumed) in kWh.")
    anomaly: bool = Field(..., description="Flag indicating if the record is an anomaly.")

    class Config:
        # Pydantic needs this to handle non-standard types like Decimal.
        json_encoders = {Decimal: float}
        # Provides an example for the auto-generated API docs.
        schema_extra = {
            "example": {
                "site_id": "site-alpha-pv-farm-01",
                "timestamp": "2025-06-13T10:00:00Z",
                "energy_generated_kwh": 150.5,
                "energy_consumed_kwh": 30.2,
                "net_energy_kwh": 120.3,
                "anomaly": False,
            }
        }
class SystemSummary(BaseModel):
    total_records: int = Field(..., description="Total number of records in the database.")
    total_anomalies: int = Field(..., description="Total number of anomalous records detected.")
    total_sites: int = Field(..., description="Total number of unique sites.")
    site_anomaly_distribution: Dict[str, int] = Field(..., description="A dictionary showing the count of anomalies for each site.")


#FastAPI Application
app = FastAPI(
    title="Private Energy Partners Data API",
    description="API for querying and summarizing energy production and consumption data.",
    version="1.0.0"
)

@app.get("/")
def read_root():
    """A simple root endpoint to confirm API is running."""
    return {"message": "Welcome to the Energy Data API."}

@app.get(
    "/summary",
    response_model=SystemSummary,
    summary="Get a high-level summary of the entire system",
    tags=["Summary Data"]
)
def get_system_summary():
    """
    Provides a summary of the entire dataset, including total records,
    total anomalies, and a breakdown of anomalies per site.

    Note:This endpoint performs a full table scan, which is not recommended
    for very large production tables due to performance and cost implications.
    """
    try:
        # A scan operation reads every item in the entire table.
        response = table.scan()
        items = response.get('Items', [])

        # Continue scanning if the table is larger than the 1MB response limit.
        while 'LastEvaluatedKey' in response:
            response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
            items.extend(response.get('Items', []))

        total_records = len(items)
        if total_records == 0:
            return {
                "total_records": 0,
                "total_anomalies": 0,
                "total_sites": 0,
                "site_anomaly_distribution": {}
            }

        anomalies = [item for item in items if item.get('anomaly')]
        site_ids = [item['site_id'] for item in items]
        
        # Use Counter for an efficient way to count anomalies per site.
        anomaly_counts = Counter(item['site_id'] for item in anomalies)

        return {
            "total_records": total_records,
            "total_anomalies": len(anomalies),
            "total_sites": len(set(site_ids)),
            "site_anomaly_distribution": dict(anomaly_counts)
        }
    except Exception as e:
        print(f"Error scanning DynamoDB: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error during table scan.")


@app.get(
    "/records/{site_id}",
    response_model=List[EnergyRecord],
    summary="Fetch records for a specific site and time range",
    tags=["Energy Data"]
)
def get_records_by_site(
    site_id: str = Path(..., description="The unique identifier for the site to query."),
    start_date: Optional[str] = Query(None, description="Start timestamp(e.g., 2025-06-10T00:00:00Z)."),
    end_date: Optional[str] = Query(None, description="End timestamp(e.g., 2025-06-12T23:59:59Z).")
):
    """
    Retrieves a list of energy records for a given site_id.
    The primary lookup is based on the site_id.
    optionally filter results to a specific time range by providing
    both start_date and end_date query parameters.
    """
    print(f"Fetching records for site_id: {site_id}")
    try:
        # The KeyConditionExpression is highly efficient for querying on partition and sort keys.
        key_condition = Key('site_id').eq(site_id)
        if start_date and end_date:
            key_condition = key_condition & Key('timestamp').between(start_date, end_date)
        
        response = table.query(KeyConditionExpression=key_condition)
        return response.get('Items', [])
    except Exception as e:
        print(f"Error querying DynamoDB: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@app.get(
    "/anomalies/{site_id}",
    response_model=List[EnergyRecord],
    summary="Retrieve all anomalies for a given site",
    tags=["Anomaly Detection"]
)
def get_anomalies_by_site(site_id: str = Path(..., description="The unique identifier for the site to check for anomalies.")):
    """
    Retrieves all records flagged as an anomaly for a specific site_id.
    """
    print(f"Fetching anomalies for site_id: {site_id}")
    try:
        # A FilterExpression is applied after the query reads data, which can be less efficient on large datasets.
        response = table.query(
            KeyConditionExpression=Key('site_id').eq(site_id),
            FilterExpression=Attr('anomaly').eq(True)
        )
        return response.get('Items', [])
    except Exception as e:
        print(f"Error querying DynamoDB for anomalies: {e}")
        raise HTTPException(status_code=500, detail="An error occurred while querying for anomalies.")
