locals {
  # Filtros reaproveitados nas consultas: transações do agente Java da API e
  # containers da API no namespace prod do cluster.
  nr_app        = "appName = 'fiap-api'"
  nr_containers = "clusterName = '${aws_eks_cluster.main.name}' AND namespaceName = 'prod' AND containerName = 'api-container'"
}

resource "newrelic_one_dashboard" "fiap_api" {
  name        = "FIAP API"
  permissions = "public_read_only"

  page {
    name = "API"

    widget_billboard {
      title  = "Requisições (30 min)"
      row    = 1
      column = 1
      width  = 4
      height = 3
      nrql_query {
        query = "SELECT count(*) FROM Transaction WHERE ${local.nr_app} SINCE 30 minutes ago"
      }
    }

    widget_billboard {
      title  = "Taxa de erro (%)"
      row    = 1
      column = 5
      width  = 4
      height = 3
      nrql_query {
        query = "SELECT percentage(count(*), WHERE error IS true) FROM Transaction WHERE ${local.nr_app} SINCE 30 minutes ago"
      }
    }

    widget_billboard {
      title  = "Latência p95 (s)"
      row    = 1
      column = 9
      width  = 4
      height = 3
      nrql_query {
        query = "SELECT percentile(duration, 95) FROM Transaction WHERE ${local.nr_app} SINCE 30 minutes ago"
      }
    }

    widget_line {
      title  = "Throughput (req/min)"
      row    = 4
      column = 1
      width  = 6
      height = 3
      nrql_query {
        query = "SELECT rate(count(*), 1 minute) FROM Transaction WHERE ${local.nr_app} TIMESERIES"
      }
    }

    widget_line {
      title  = "Latência média e p95 (s)"
      row    = 4
      column = 7
      width  = 6
      height = 3
      nrql_query {
        query = "SELECT average(duration), percentile(duration, 95) FROM Transaction WHERE ${local.nr_app} TIMESERIES"
      }
    }

    widget_area {
      title  = "Respostas por status HTTP"
      row    = 7
      column = 1
      width  = 6
      height = 3
      nrql_query {
        query = "SELECT count(*) FROM Transaction WHERE ${local.nr_app} FACET http.statusCode TIMESERIES"
      }
    }

    widget_table {
      title  = "Endpoints mais lentos"
      row    = 7
      column = 7
      width  = 6
      height = 3
      nrql_query {
        query = "SELECT count(*), average(duration), percentile(duration, 95) FROM Transaction WHERE ${local.nr_app} FACET name LIMIT 10"
      }
    }
  }

  page {
    name = "Kubernetes"

    widget_line {
      title  = "CPU por pod (cores)"
      row    = 1
      column = 1
      width  = 6
      height = 3
      nrql_query {
        query = "SELECT average(cpuUsedCores) FROM K8sContainerSample WHERE ${local.nr_containers} FACET podName TIMESERIES"
      }
    }

    widget_line {
      title  = "Memória por pod (bytes)"
      row    = 1
      column = 7
      width  = 6
      height = 3
      nrql_query {
        query = "SELECT average(memoryWorkingSetBytes) FROM K8sContainerSample WHERE ${local.nr_containers} FACET podName TIMESERIES"
      }
    }

    widget_line {
      title  = "Pods da API em execução (HPA)"
      row    = 4
      column = 1
      width  = 6
      height = 3
      nrql_query {
        query = "SELECT uniqueCount(podName) FROM K8sContainerSample WHERE ${local.nr_containers} TIMESERIES"
      }
    }

    widget_table {
      title  = "Restarts por pod"
      row    = 4
      column = 7
      width  = 6
      height = 3
      nrql_query {
        query = "SELECT latest(restartCount) FROM K8sContainerSample WHERE ${local.nr_containers} FACET podName"
      }
    }
  }
}

output "newrelic_dashboard_url" {
  value = newrelic_one_dashboard.fiap_api.permalink
}
