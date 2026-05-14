# Implementation Spec: k8s_config

## Module

Implement a single Python module `k8s_config.py` containing three builder classes: `ContainerSpecBuilder`, `DeploymentBuilder`, and `ServiceBuilder`.

The module must use `logging` (not `print`) for any diagnostic output. No YAML serialization inside the module — callers handle that.

## Dependencies

The module imports from the `k8s_core` package:

```python
from k8s_core import (
    ContainerSpec,
    DeploymentSpec,
    ResourceRequirements,
    SecurityContext,
    ServiceSpec,
)
from k8s_core.exceptions import ConfigError
```

## Class 1: ContainerSpecBuilder

Stateless builder class. Assembles a container specification for a single container.

### Method

```python
def build(
    self,
    name: str,
    image: str,
    cpu_limit: str,
    memory_limit: str,
    cpu_request: str | None = None,
    memory_request: str | None = None,
    run_as_uid: int = 1000,
    writable_paths: list[str] | None = None,
    env: dict[str, str] | None = None,
) -> ContainerSpec
```

**Behavior:**

Returns a `ContainerSpec` with:
- `name` set from the `name` parameter
- `image` set from the `image` parameter
- `resources` set to a `ResourceRequirements` with:
  - `limits["cpu"]` equal to `cpu_limit`
  - `limits["memory"]` equal to `memory_limit`
  - `requests` populated from `cpu_request` and `memory_request` if provided
- `security_context` set to a `SecurityContext` with:
  - `run_as_non_root=True`
  - `run_as_user` equal to `run_as_uid`
  - `allow_privilege_escalation=False`
  - `read_only_root_filesystem=True` when `writable_paths` is `None` or empty
  - `read_only_root_filesystem=False` when `writable_paths` is non-empty
- `env` populated from the `env` parameter (empty dict if not provided)

**Raises:**
- `ConfigError` if `run_as_uid` is `0`
- `ConfigError` if `cpu_limit` is an empty string
- `ConfigError` if `memory_limit` is an empty string

## Class 2: DeploymentBuilder

Assembles a complete Kubernetes Deployment specification.

### Method

```python
def build(
    self,
    name: str,
    namespace: str,
    image: str,
    replicas: int,
    cpu_limit: str,
    memory_limit: str,
    labels: dict[str, str] | None = None,
    annotations: dict[str, str] | None = None,
    run_as_uid: int = 1000,
    writable_paths: list[str] | None = None,
    env: dict[str, str] | None = None,
) -> DeploymentSpec
```

**Behavior:**

1. Builds a `ContainerSpec` for the named container using `ContainerSpecBuilder`.
2. Returns a `DeploymentSpec` with:
   - `name` set from the `name` parameter
   - `namespace` set from the `namespace` parameter
   - `replicas` set from the `replicas` parameter
   - `containers` containing the single `ContainerSpec` built above
   - `labels` set from the `labels` parameter (defaults to `{"app": name}` if not provided)
   - `annotations` set from the `annotations` parameter (defaults to empty dict)

**Raises:**
- `ConfigError` if `replicas` is less than `1`
- `ConfigError` if `namespace` is an empty string
- Propagates `ConfigError` from `ContainerSpecBuilder` unchanged

## Class 3: ServiceBuilder

Assembles a Kubernetes Service specification.

### Method

```python
def build(
    self,
    name: str,
    namespace: str,
    selector: dict[str, str],
    port: int,
    target_port: int,
    service_type: str = "ClusterIP",
) -> ServiceSpec
```

**Behavior:**

Returns a `ServiceSpec` with all fields set from the corresponding parameters.

**Raises:**
- `ConfigError` if `selector` is an empty dict
- `ConfigError` if `port` is not in the range `1` to `65535` inclusive
- `ConfigError` if `target_port` is not in the range `1` to `65535` inclusive
- `ConfigError` if `service_type` is not one of `"ClusterIP"`, `"NodePort"`, or `"LoadBalancer"`
