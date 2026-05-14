# Test Goals: k8s_config

## ContainerSpecBuilder.build — Happy Path

- Returns a value when called with valid parameters
- The returned value's `name` attribute matches the `name` argument
- The returned value's `image` attribute matches the `image` argument
- `result.resources.limits["cpu"]` equals the `cpu_limit` argument
- `result.resources.limits["memory"]` equals the `memory_limit` argument
- When `cpu_request` is provided, `result.resources.requests["cpu"]` equals `cpu_request`
- When `memory_request` is provided, `result.resources.requests["memory"]` equals `memory_request`
- `result.security_context.run_as_non_root` is `True`
- `result.security_context.run_as_user` equals the `run_as_uid` argument
- `result.security_context.run_as_user` is `1000` when `run_as_uid` is not provided
- `result.security_context.allow_privilege_escalation` is `False`
- `result.security_context.read_only_root_filesystem` is `True` when `writable_paths` is `None`
- `result.security_context.read_only_root_filesystem` is `True` when `writable_paths` is an empty list
- `result.security_context.read_only_root_filesystem` is `False` when `writable_paths` is non-empty
- When `env` is provided, the returned spec's `env` dict matches the `env` argument
- When `env` is not provided, the returned spec's `env` is an empty dict

## ContainerSpecBuilder.build — Validation

- Raises `ConfigError` when `run_as_uid` is `0`
- Raises `ConfigError` when `cpu_limit` is an empty string `""`
- Raises `ConfigError` when `memory_limit` is an empty string `""`

## DeploymentBuilder.build — Happy Path

- Returns a value when called with valid parameters
- `result.name` matches the `name` argument
- `result.namespace` matches the `namespace` argument
- `result.replicas` matches the `replicas` argument
- `result.containers` contains exactly one container
- The container in `result.containers` has `name` matching the `name` argument
- The container in `result.containers` has `image` matching the `image` argument
- The container's `resources.limits["cpu"]` matches the `cpu_limit` argument
- The container's `resources.limits["memory"]` matches the `memory_limit` argument
- The container's `security_context.run_as_non_root` is `True`
- The container's `security_context.allow_privilege_escalation` is `False`
- When `labels` is provided, `result.labels` matches the `labels` argument
- When `labels` is not provided, `result.labels` contains `{"app": name}`
- When `annotations` is not provided, `result.annotations` is an empty dict

## DeploymentBuilder.build — Validation

- Raises `ConfigError` when `replicas` is `0`
- Raises `ConfigError` when `replicas` is `-1`
- Raises `ConfigError` when `namespace` is an empty string `""`

## ServiceBuilder.build — Happy Path

- Returns a value when called with valid parameters
- `result.name` matches the `name` argument
- `result.namespace` matches the `namespace` argument
- `result.selector` matches the `selector` argument
- `result.port` matches the `port` argument
- `result.target_port` matches the `target_port` argument
- `result.service_type` is `"ClusterIP"` when `service_type` is not provided
- `result.service_type` is `"NodePort"` when `service_type="NodePort"` is passed
- `result.service_type` is `"LoadBalancer"` when `service_type="LoadBalancer"` is passed

## ServiceBuilder.build — Validation

- Raises `ConfigError` when `selector` is an empty dict `{}`
- Raises `ConfigError` when `port` is `0`
- Raises `ConfigError` when `port` is `65536`
- Raises `ConfigError` when `target_port` is `0`
- Raises `ConfigError` when `target_port` is `-1`
- Raises `ConfigError` when `service_type` is `"ExternalName"`
- Raises `ConfigError` when `service_type` is `""`

## Type Integrity

- All exceptions raised by `ContainerSpecBuilder.build` are instances of `ConfigError`
- All exceptions raised by `DeploymentBuilder.build` are instances of `ConfigError`
- All exceptions raised by `ServiceBuilder.build` are instances of `ConfigError`
- The value returned by `ContainerSpecBuilder.build` is an instance of `k8s_core.ContainerSpec`
- The value returned by `DeploymentBuilder.build` is an instance of `k8s_core.DeploymentSpec`
- The value returned by `ServiceBuilder.build` is an instance of `k8s_core.ServiceSpec`
- `result.resources` from `ContainerSpecBuilder.build` is an instance of `k8s_core.ResourceRequirements`
- `result.security_context` from `ContainerSpecBuilder.build` is an instance of `k8s_core.SecurityContext`
- The container in `DeploymentBuilder.build` result is an instance of `k8s_core.ContainerSpec`
