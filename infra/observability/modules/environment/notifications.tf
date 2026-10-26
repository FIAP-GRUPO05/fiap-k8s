resource "newrelic_nrql_alert_condition" "notification_failures" {
  policy_id                    = newrelic_alert_policy.fiap_api.id
  type                         = "static"
  name                         = "Falhas de notificacao (${var.environment})"
  enabled                      = true
  violation_time_limit_seconds = 3600
  aggregation_window           = 60
  aggregation_method           = "event_flow"
  aggregation_delay            = 120
  fill_option                  = "static"
  fill_value                   = 0
  nrql {
    query = "SELECT count(*) FROM Log WHERE ${local.nr_logs} AND level = 'ERROR' AND logger_name LIKE '%ServiceOrderStatusChangedNotificationHandler'"
  }
  critical {
    operator              = "above"
    threshold             = 0
    threshold_duration    = 60
    threshold_occurrences = "at_least_once"
  }
}
