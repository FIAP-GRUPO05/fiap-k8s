resource "newrelic_nrql_alert_condition" "notification_failures" {
  policy_id                    = newrelic_alert_policy.fiap_api.id
  type                         = "static"
  name                         = "Falhas de notificacao (${var.environment})"
  enabled                      = true
  violation_time_limit_seconds = 3600
  aggregation_window           = 60
  # event_timer fecha cada janela 60 s após o último evento: erros são esporádicos e,
  # com event_flow, as janelas sem eventos novos nunca eram avaliadas (incidente não fechava).
  aggregation_method             = "event_timer"
  aggregation_timer              = 60
  fill_option                    = "static"
  fill_value                     = 0
  expiration_duration            = 300
  open_violation_on_expiration   = false
  close_violations_on_expiration = true
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
