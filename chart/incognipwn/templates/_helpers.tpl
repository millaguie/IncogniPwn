{{- define "incognipwn.fullname" -}}
{{- .Release.Name -}}
{{- end -}}

{{- define "incognipwn.labels" -}}
app.kubernetes.io/name: {{ include "incognipwn.fullname" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{- define "incognipwn.selectorLabels" -}}
app.kubernetes.io/name: {{ include "incognipwn.fullname" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}
