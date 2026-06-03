import azure.functions as func
from azure.data.tables import TableServiceClient
import requests
import datetime
import json
import os
import logging
 
def main(mytimer: func.TimerRequest) -> None:
    """
    Runs every 5 minutes. Checks the target website for:
    1. Reachability (does the server respond at all?)
    2. Response time (is it fast enough to be usable?)
    3. Content validity (is the right content present?)
    Writes every check result to Azure Table Storage.
    """
    target_url    = os.environ["TARGET_URL"]
    storage_conn  = os.environ["AzureWebJobsStorage"]
    check_time    = datetime.datetime.utcnow()
    result_status = "PASS"
    error_detail  = None
    response_ms   = None
 
    try:
        # Make the HTTP request with a 10-second timeout
        # If the site takes longer than 10 seconds, treat it as a failure
        response = requests.get(target_url, timeout=10)
        response_ms = response.elapsed.total_seconds() * 1000
 
        # Check 1: Did the server respond with a success code?
        if response.status_code != 200:
            result_status = "FAIL"
            error_detail  = f"HTTP {response.status_code}"
 
        # Check 2: Was the response time under 5 seconds?
        # Sites that take over 5 seconds are functionally down for most users
        elif response_ms > 5000:
            result_status = "SLOW"
            error_detail  = f"Response time {response_ms:.0f}ms exceeded 5000ms threshold"
 
        # Check 3: Does the response contain expected content?
        # This catches cases where the server responds but shows an error page
        elif "error" in response.text.lower() and "404" in response.text:
            result_status = "FAIL"
            error_detail  = "Page contains error indicators"
 
    except requests.exceptions.ConnectionError:
        result_status = "FAIL"
        error_detail  = "Connection refused — server unreachable"
    except requests.exceptions.Timeout:
        result_status = "FAIL"
        error_detail  = "Request timed out after 10 seconds"
    except Exception as e:
        result_status = "FAIL"
        error_detail  = str(e)
 
    # Write the result to Azure Table Storage
    # Every check gets its own row with a timestamp-based row key
    table_service = TableServiceClient.from_connection_string(storage_conn)
    table_client  = table_service.get_table_client("uptimechecks")
 
    entity = {
        "PartitionKey": target_url,
        "RowKey":       check_time.strftime("%Y%m%d%H%M%S"),
        "Timestamp":    check_time.isoformat(),
        "Status":       result_status,
        "ResponseMs":   int(response_ms) if response_ms else 0,
        "ErrorDetail":  error_detail or "",
        "TargetUrl":    target_url,
    }
 
    try:
        table_client.create_table_if_not_exists()
        table_client.upsert_entity(entity)
        logging.info(f"Check result: {result_status} | {response_ms:.0f}ms | {target_url}")
    except Exception as e:
        logging.error(f"Failed to write result to table: {e}")
 
    # Log failures prominently so they appear in Application Insights
    if result_status != "PASS":
        logging.error(f"SITE DOWN: {target_url} | {result_status} | {error_detail}")
