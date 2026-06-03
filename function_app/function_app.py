import azure.functions as func
from azure.data.tables import TableServiceClient
import requests
import datetime
import os
import logging

app = func.FunctionApp()

@app.timer_trigger(schedule="0 */5 * * * *", 
                   arg_name="mytimer", 
                   run_on_startup=False)
def check_website(mytimer: func.TimerRequest) -> None:
    target_url    = os.environ["TARGET_URL"]
    storage_conn  = os.environ["AzureWebJobsStorage"]
    check_time    = datetime.datetime.utcnow()
    result_status = "PASS"
    error_detail  = None
    response_ms   = None

    try:
        response    = requests.get(target_url, timeout=10)
        response_ms = response.elapsed.total_seconds() * 1000

        if response.status_code != 200:
            result_status = "FAIL"
            error_detail  = f"HTTP {response.status_code}"
        elif response_ms > 5000:
            result_status = "SLOW"
            error_detail  = f"Response time {response_ms:.0f}ms exceeded 5000ms"
        elif "error" in response.text.lower() and "404" in response.text:
            result_status = "FAIL"
            error_detail  = "Page contains error indicators"

    except requests.exceptions.ConnectionError:
        result_status = "FAIL"
        error_detail  = "Connection refused"
    except requests.exceptions.Timeout:
        result_status = "FAIL"
        error_detail  = "Request timed out after 10 seconds"
    except Exception as e:
        result_status = "FAIL"
        error_detail  = str(e)

    table_service = TableServiceClient.from_connection_string(storage_conn)
    table_client  = table_service.get_table_client("uptimechecks")

    entity = {
        "PartitionKey": target_url.replace("https://", "").replace("http://", "").replace("/", "_"),        "RowKey":       check_time.strftime("%Y%m%d%H%M%S"),
        "Timestamp":    check_time.isoformat(),
        "Status":       result_status,
        "ResponseMs":   int(response_ms) if response_ms else 0,
        "ErrorDetail":  error_detail or "",
        "TargetUrl":    target_url,
    }

    try:
        table_client.create_table_if_not_exists("uptimechecks")
    except Exception:
        pass
        table_client.upsert_entity(entity)
        logging.info(f"Check result: {result_status} | {response_ms:.0f}ms | {target_url}")
    except Exception as e:
        logging.error(f"Failed to write to table: {e}")

    if result_status != "PASS":
        logging.error(f"SITE DOWN: {target_url} | {result_status} | {error_detail}")