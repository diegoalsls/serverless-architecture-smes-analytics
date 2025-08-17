{
  "Comment": "ETL + Predicción",
  "StartAt": "RunPrediction",
  "States": {
    "RunPrediction": {
      "Type": "Task",
      "Resource": "${prediction_lambda_arn}",
      "End": true
    }
  }
}

