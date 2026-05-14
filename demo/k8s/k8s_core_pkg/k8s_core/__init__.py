"""K8s Secure Deployment shared core — canonical typed config objects.

Per the K8s Secure Deployment Platform Architecture Document (SAD Section 6.5),
all config builders must assemble Kubernetes configuration fragments using these
typed dataclasses rather than raw dict literals. Serialization to dict (for YAML
output) occurs only via the to_dict() methods defined here.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from k8s_core.exceptions import ConfigError, K8sConfigError

__all__ = [
    "ResourceRequirements",
    "SecurityContext",
    "ContainerSpec",
    "DeploymentSpec",
    "ServiceSpec",
    "ConfigError",
    "K8sConfigError",
]


@dataclass
class ResourceRequirements:
    """CPU and memory resource limits and requests for a container."""

    limits: dict[str, str]
    requests: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Serialize to Kubernetes-compatible dict."""
        result: dict = {"limits": self.limits}
        if self.requests:
            result["requests"] = self.requests
        return result


@dataclass
class SecurityContext:
    """Pod/container security context enforcing the Secure Deployment Baseline."""

    run_as_non_root: bool
    run_as_user: int
    allow_privilege_escalation: bool
    read_only_root_filesystem: bool

    def to_dict(self) -> dict:
        """Serialize to Kubernetes-compatible dict."""
        return {
            "runAsNonRoot": self.run_as_non_root,
            "runAsUser": self.run_as_user,
            "allowPrivilegeEscalation": self.allow_privilege_escalation,
            "readOnlyRootFilesystem": self.read_only_root_filesystem,
        }


@dataclass
class ContainerSpec:
    """A single container specification within a pod template."""

    name: str
    image: str
    resources: ResourceRequirements
    security_context: SecurityContext
    env: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.resources, ResourceRequirements):
            raise TypeError(
                f"resources must be ResourceRequirements, got {type(self.resources).__name__}"
            )
        if not isinstance(self.security_context, SecurityContext):
            raise TypeError(
                f"security_context must be SecurityContext, got {type(self.security_context).__name__}"
            )

    def to_dict(self) -> dict:
        """Serialize to Kubernetes-compatible dict."""
        result: dict = {
            "name": self.name,
            "image": self.image,
            "resources": self.resources.to_dict(),
            "securityContext": self.security_context.to_dict(),
        }
        if self.env:
            result["env"] = [{"name": k, "value": v} for k, v in self.env.items()]
        return result


@dataclass
class DeploymentSpec:
    """A Kubernetes Deployment specification."""

    name: str
    namespace: str
    replicas: int
    containers: list[ContainerSpec]
    labels: dict[str, str] = field(default_factory=dict)
    annotations: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Serialize to Kubernetes-compatible Deployment manifest dict."""
        pod_labels = self.labels or {"app": self.name}
        return {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": self.name,
                "namespace": self.namespace,
                "annotations": self.annotations,
            },
            "spec": {
                "replicas": self.replicas,
                "selector": {"matchLabels": pod_labels},
                "template": {
                    "metadata": {"labels": pod_labels},
                    "spec": {
                        "containers": [c.to_dict() for c in self.containers],
                    },
                },
            },
        }


@dataclass
class ServiceSpec:
    """A Kubernetes Service specification."""

    name: str
    namespace: str
    selector: dict[str, str]
    port: int
    target_port: int
    service_type: str = "ClusterIP"

    def to_dict(self) -> dict:
        """Serialize to Kubernetes-compatible Service manifest dict."""
        return {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {
                "name": self.name,
                "namespace": self.namespace,
            },
            "spec": {
                "type": self.service_type,
                "selector": self.selector,
                "ports": [
                    {
                        "port": self.port,
                        "targetPort": self.target_port,
                    }
                ],
            },
        }
