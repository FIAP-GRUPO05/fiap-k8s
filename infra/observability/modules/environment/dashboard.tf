locals {

  nr_app            = "appName = 'fiap-api-${var.environment}'"
  nr_api            = "${local.nr_app} AND transactionType = 'Web' AND request.uri NOT LIKE '%/actuator%'"
  nr_service_orders = "${local.nr_api} AND request.uri LIKE '%/service-orders%'"

  nr_containers = "clusterName = '${var.cluster_name}' AND namespaceName = '${var.environment}' AND containerName = 'api-container'"

  nr_logs = "cluster_name = '${var.cluster_name}' AND namespace_name = '${var.environment}' AND container_name = 'api-container'"

  nr_service_order_alert_name = "Falhas no processamento de ordens de serviço (${var.environment})"

}

# Alerta sem notificação: o incidente fica só no New Relic (Alerts > Issues) e no dashboard
resource "newrelic_alert_policy" "fiap_api" {
  name                = "FIAP API (${var.environment})"
  incident_preference = "PER_CONDITION"
}

# Abre incidente quando um endpoint de OS responde 5xx; fecha após 1 minuto sem falhas
resource "newrelic_nrql_alert_condition" "service_order_failures" {
  policy_id                    = newrelic_alert_policy.fiap_api.id
  type                         = "static"
  name                         = local.nr_service_order_alert_name
  enabled                      = true
  violation_time_limit_seconds = 3600
  aggregation_window           = 60
  aggregation_method           = "event_flow"
  aggregation_delay            = 120
  fill_option                  = "static"
  fill_value                   = 0

  nrql {
    query = "SELECT count(*) FROM Transaction WHERE ${local.nr_service_orders} AND http.statusCode >= 500"
  }

  critical {
    operator              = "above"
    threshold             = 0
    threshold_duration    = 60
    threshold_occurrences = "at_least_once"
  }
}

resource "newrelic_one_dashboard" "fiap_api" {
  name        = "FIAP API (${var.environment})"
  permissions = "private"

  page {
    name = "Monitoramento"

    widget_line {
      title  = "Latência das APIs (ms)"
      row    = 1
      column = 1
      width  = 6
      height = 3
      nrql_query {
        query = "SELECT average(duration * 1000) AS 'média', percentile(duration * 1000, 95) FROM Transaction WHERE ${local.nr_api} TIMESERIES"
      }
    }

    widget_billboard {
      title  = "Disponibilidade dos pods (%)"
      row    = 1
      column = 7
      width  = 6
      height = 3
      nrql_query {
        query = "SELECT percentage(count(*), WHERE isReady = true) AS 'amostras prontas' FROM K8sPodSample WHERE clusterName = '${var.cluster_name}' AND namespaceName = '${var.environment}' AND podName LIKE 'api-deployment%'"
      }
    }

    widget_line {
      title  = "CPU por pod (cores)"
      row    = 4
      column = 1
      width  = 6
      height = 3
      nrql_query {
        query = "SELECT average(cpuUsedCores) FROM K8sContainerSample WHERE ${local.nr_containers} FACET podName TIMESERIES"
      }
    }

    widget_line {
      title  = "Memória por pod (MB)"
      row    = 4
      column = 7
      width  = 6
      height = 3
      nrql_query {
        query = "SELECT average(memoryWorkingSetBytes) / 1e6 FROM K8sContainerSample WHERE ${local.nr_containers} FACET podName TIMESERIES"
      }
    }

    widget_line {
      title  = "Falhas no processamento de ordens de serviço (5xx)"
      row    = 7
      column = 1
      width  = 6
      height = 3
      nrql_query {
        query = "SELECT count(*) FROM Transaction WHERE ${local.nr_service_orders} AND http.statusCode >= 500 TIMESERIES"
      }
    }

    widget_table {
      title  = "Logs (JSON) com correlação"
      row    = 7
      column = 7
      width  = 6
      height = 3
      nrql_query {
        query = "SELECT correlationId, timestamp, level, message, trace.id FROM Log WHERE ${local.nr_logs} LIMIT 100"
      }
    }

    widget_table {
      title  = "Alertas de falhas no processamento de ordens de serviço"
      row    = 10
      column = 1
      width  = 12
      height = 3
      nrql_query {
        query = "SELECT timestamp, event AS 'evento', priority AS 'prioridade', title AS 'incidente' FROM NrAiIncident WHERE conditionName = '${local.nr_service_order_alert_name}' LIMIT 50"
      }
    }
  }

  page {
    name = "Ordens de serviço"

    widget_stacked_bar {
      title  = "Volume diário de ordens de serviço abertas"
      row    = 1
      column = 1
      width  = 6
      height = 3
      nrql_query {
        query = "SELECT count(*) FROM ServiceOrderStatusChanged WHERE appName = 'fiap-api-${var.environment}' AND newStatus = 'RECEIVED' SINCE 7 days ago TIMESERIES 1 day"
      }
    }

    widget_billboard {
      title  = "Tempo médio de execução por status (min)"
      row    = 1
      column = 7
      width  = 6
      height = 3
      nrql_query {
        query = "SELECT filter(average(timeInPreviousStatusSeconds), WHERE previousStatus = 'IN_DIAGNOSIS') / 60 AS 'Diagnóstico', filter(average(timeInPreviousStatusSeconds), WHERE previousStatus = 'IN_EXECUTION') / 60 AS 'Execução', filter(average(timeInPreviousStatusSeconds), WHERE previousStatus = 'FINALIZED') / 60 AS 'Finalização' FROM ServiceOrderStatusChanged WHERE appName = 'fiap-api-${var.environment}' SINCE 7 days ago"
      }
    }

    widget_table {
      title  = "Erros e falhas nas integrações"
      row    = 4
      column = 1
      width  = 12
      height = 3
      nrql_query {
        query = "SELECT count(*) AS 'falhas', latest(message) AS 'última mensagem' FROM Log WHERE ${local.nr_logs} AND level = 'ERROR' AND logger_name LIKE '%ServiceOrderStatusChangedNotificationHandler' FACET capture(stack_trace, r'(?s)(?P<erro>[^:]+):.*') AS 'erro'"
      }
    }
  }
}

output "newrelic_dashboard_url" {
  value = newrelic_one_dashboard.fiap_api.permalink
}
