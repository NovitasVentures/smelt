# Software Architecture Document (SAD): K8s Secure Deployment Platform
**Standard:** ISO/IEC/IEEE 42010:2011  
**Subject:** Kubernetes Configuration Generation Library — Secure Deployment Baseline  
**Version:** 1.0  

---

## 1. Introduction and System Context
The K8s Secure Deployment Platform is a Python configuration generation library used by platform engineers at an organization running a multi-tenant Kubernetes cluster. It generates Deployment, Service, and related manifest dictionaries for internal services. All generated manifests must comply with the organization's **Secure Deployment Baseline** — a set of non-negotiable security controls codified in this document and enforced through automated tooling. This document serves as the primary architectural guidance for all engineers contributing to the platform.

---

## 2. Stakeholders and Concerns
Per ISO 42010, this architecture is designed to address the specific concerns of the following stakeholders:

| Stakeholder | Concerns |
| :--- | :--- |
| **Platform Engineer** | Correctness, reproducibility, type safety across manifest types, and maintainable config generation code. |
| **Security Team** | Guaranteed hardening posture: no root containers, no privilege escalation, enforced resource isolation, immutable container filesystems. |
| **SRE / Operations** | Resource limit enforcement prevents noisy-neighbor failures; read-only root filesystems reduce blast radius of a compromised container. |
| **Service Owner** | Predictable, typed API for specifying deployment requirements without needing to know Kubernetes security internals. |

---

## 3. Use Case View (Architectural Drivers)
These scenarios define the primary functional requirements that the architecture must satisfy.

### UC-1: Stateless Service Deployment
- **Actor:** Platform Engineer
- **Flow:**
    1. Engineer calls `ContainerSpecBuilder.build()` with service name, image, and resource limits.
    2. Builder returns a `ContainerSpec` with security baseline applied.
    3. Engineer passes the spec to `DeploymentBuilder.build()` to produce a `DeploymentSpec`.
    4. Engineer calls `.to_dict()` on the `DeploymentSpec` and serializes to YAML.
- **Constraint:** The generated manifest must satisfy all five Secure Deployment Baseline principles without additional caller configuration.

### UC-2: Service with Writable Ephemeral Paths
- **Actor:** Platform Engineer
- **Flow:**
    1. Engineer calls `ContainerSpecBuilder.build()` with `writable_paths=["/tmp", "/var/log"]`.
    2. Builder sets `readOnlyRootFilesystem=False` and signals the caller to mount emptyDir volumes at those paths.
    3. All other security baseline properties (non-root, no escalation, resource limits) remain unconditionally enforced.
- **Constraint:** The writable-paths exception path must not weaken any of the other four security principles.

---

## 4. Logical View (Component Taxonomy)
The library is decomposed into three builder components and one shared types package.

1. **ContainerSpecBuilder:** Assembles a complete container specification including resources and security context. Enforces all security baseline constraints directly.
2. **DeploymentBuilder:** Orchestrates a complete Deployment manifest. Delegates container spec assembly to `ContainerSpecBuilder`.
3. **ServiceBuilder:** Produces Service manifests. Validates networking parameters and service type.
4. **k8s_core (shared package):** Canonical typed dataclasses for `ResourceRequirements`, `SecurityContext`, `ContainerSpec`, `DeploymentSpec`, and `ServiceSpec`. The single source of structural truth.

---

## 5. Process View (System Dynamics)
The generation pipeline is single-threaded and synchronous. Manifests are assembled entirely in memory using typed `k8s_core` objects. No external API calls or Kubernetes cluster connections occur during config generation. Serialization to YAML is the caller's responsibility and occurs only after the typed object graph is fully constructed.

---

## 6. Development View (Architectural Principles)
To satisfy the **Security Team** and **Platform Engineer** stakeholder concerns, all builder components must adhere to these five core principles.

### 6.1 Principle: Resource Bounds Required (RBR)
Every container specification must declare both CPU and memory resource limits unconditionally. The platform cannot guarantee fair scheduling or prevent noisy-neighbor interference without hard resource bounds on every workload.
- **Guideline:** Set both `resources.limits.cpu` and `resources.limits.memory` unconditionally in every container spec assembly function. Do not make limit fields conditional on caller-supplied parameters being non-None. Raise `ConfigError` if either limit is missing.
- **Rationale:** Resource starvation in a shared cluster is a reliability failure, not a best-effort concern. A container with no limits can consume all CPU on a node and starve other workloads.

### 6.2 Principle: Non-Root Enforcement (NRE)
Every container security context must explicitly set `runAsNonRoot` to `true` and `runAsUser` to a non-zero integer UID. These fields must be present and assigned unconditionally.
- **Guideline:** Always set `run_as_non_root=True` and `run_as_user` to the provided UID (defaulting to 1000). Raise `ConfigError` if a UID of 0 (root) is supplied. Never make these fields conditional on caller parameters.
- **Rationale:** The Kubernetes default permits containers to run as root. An explicit non-root declaration is required for every workload. A container running as root can trivially escape to the host in certain kernel vulnerability scenarios.

### 6.3 Principle: Privilege Escalation Block (PAB)
Every container security context must unconditionally set `allowPrivilegeEscalation` to `false`. This field must be explicitly denied — never omitted and never conditional.
- **Guideline:** Always set `allow_privilege_escalation=False` in every security context. This field must not be gated on any caller-supplied parameter.
- **Rationale:** Kubernetes defaults to allowing privilege escalation (via setuid binaries). An explicit `allowPrivilegeEscalation: false` blocks this class of escalation entirely. Omitting the field means relying on a default that is insecure.

### 6.4 Principle: Immutable Root Filesystem (IRR)
Container security contexts must set `readOnlyRootFilesystem` to `true` unconditionally, with the explicit documented exception of containers that register writable paths via the `writable_paths` parameter (which triggers emptyDir volume mounts instead).
- **Guideline:** Set `read_only_root_filesystem=True` unless `writable_paths` is non-empty. When `writable_paths` is provided, set `read_only_root_filesystem=False` and return the list so the caller can mount emptyDir volumes at those paths.
- **Rationale:** A writable root filesystem allows an attacker with code execution to persist tools and modify binaries. emptyDir volumes provide the writable scratch space applications need without permanently modifying the container image layer.

### 6.5 Principle: Typed Configuration Objects (TCO)
Kubernetes configuration fragments — `ResourceRequirements`, `SecurityContext`, `ContainerSpec`, and `DeploymentSpec` — must be assembled using the typed dataclasses from the `k8s_core` package. Raw dict literals must not be constructed in place of these types in any business logic function.
- **Guideline:** Import and instantiate `k8s_core.ResourceRequirements`, `k8s_core.SecurityContext`, `k8s_core.ContainerSpec`, and `k8s_core.DeploymentSpec` directly. The conversion to a plain dict occurs only in the `.to_dict()` methods defined within `k8s_core`.
- **Rationale:** Raw dict construction bypasses the type system and the `__post_init__` validation in each dataclass. It allows structural drift — e.g., using the wrong key name, omitting a required field — that would be caught at construction time by the typed interface. Type safety across the manifest generation pipeline is a non-negotiable property.

---

## 7. Architectural Decision Records (ADRs)

### ADR-001: k8s_core as a Separate Installable Package
- **Decision:** The five canonical K8s config types live in a standalone `k8s-core` package installed as a dependency, not defined inline in the config builder module.
- **Rationale:** Multiple config-generating modules (deployment configs, job configs, CronJob configs) must share these types. Inlining them creates the exact schema drift that TCO is designed to prevent. A separate package makes the single-source-of-truth contractual rather than advisory.

### ADR-002: YAML Serialization at the Caller Boundary Only
- **Decision:** Builder classes return typed `k8s_core` objects. Callers invoke `.to_dict()` and then `yaml.dump()`. The builder module does not import `yaml`.
- **Rationale:** Separating the config graph construction from serialization keeps the builders testable without YAML dependencies and makes the typed object graph available for programmatic inspection (e.g., policy enforcement tooling) before serialization.

---

## 8. Quality Attributes
- **Security:** Guaranteed by RBR, NRE, PAB, and IRR — the four mandatory principles of the Secure Deployment Baseline.
- **Maintainability:** Guaranteed by TCO — type-safe config construction with validation at object construction time.
- **Reliability:** Resource starvation failures prevented by RBR. Container isolation strengthened by PAB and IRR.
- **Testability:** Each builder can be tested independently; `k8s_core` objects have predictable structure; no external dependencies during config generation.
