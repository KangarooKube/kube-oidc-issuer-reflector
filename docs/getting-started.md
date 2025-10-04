# Getting Started

## Prerequisites

1. **Environment Variables**:
   - `$OIDC_ISSUER_FQDN`: Fully qualified domain name for the OIDC issuer.

2. **Registered Domain**:
   - Ensure you have a registered domain with a sub-domain name that points to your Kubernetes cluster's OIDC issuer FQDN (`$OIDC_ISSUER_FQDN`).
   - Ensure the FQDN is resolvable and reachable from the internet


## Setting Up a MicroK8s Cluster

1. Install MicroK8s:
   ```bash
   sudo snap install microk8s --classic
   ```

2. Enable required MicroK8s add-ons:
   ```bash
   microk8s enable dns storage
   ```

3. Configure the Kubernetes API server with OIDC parameters:
   - Edit the MicroK8s configuration file:
     ```bash
     sudo nano /var/snap/microk8s/current/args/kube-apiserver
     ```
   - Add the following lines to the file:
     ```bash
     --service-account-jwks-uri=https://$OIDC_ISSUER_FQDN/openid/v1/jwks
     --service-account-issuer=https://$OIDC_ISSUER_FQDN
     ```

4. Restart MicroK8s to apply the changes:
   ```bash
   sudo microk8s stop
   sudo microk8s start
   ```

5. Add your user to the `microk8s` group to avoid using `sudo`:
   ```bash
   sudo usermod -aG microk8s $USER
   newgrp microk8s
   ```

6. Verify the cluster is running:
   ```bash
   microk8s status --wait-ready
   ```

7. Alias `kubectl` to use MicroK8s' built-in `kubectl`:
   ```bash
   alias kubectl="microk8s kubectl"
   ```

## Setting Up a CoreDNS CNAME for `$OIDC_ISSUER_FQDN`

To ensure `$OIDC_ISSUER_FQDN` resolves to the Kubernetes API service within the cluster, you can configure a CoreDNS override.

1. Edit the CoreDNS ConfigMap:
   ```bash
   kubectl -n kube-system edit configmap coredns
   ```

2. Add the following entry under the `data.Corefile` section:
   ```yaml
   data:
     Corefile: |
       .:53 {
           errors
           health
           ready
           kubernetes cluster.local in-addr.arpa ip6.arpa {
               pods insecure
               fallthrough in-addr.arpa ip6.arpa
           }
           hosts {
               $OIDC_ISSUER_FQDN kubernetes.default.svc.cluster.local
               fallthrough
           }
           prometheus :9153
           forward . /etc/resolv.conf
           cache 30
           loop
           reload
           loadbalance
       }
   ```

3. Save and exit the editor.

4. Restart the CoreDNS pods to apply the changes:
   ```bash
   kubectl -n kube-system rollout restart deployment/coredns
   ```

5. Verify the DNS resolution:
   ```bash
   kubectl run -it --rm dns-test --image=busybox --restart=Never -- nslookup $OIDC_ISSUER_FQDN
   ```

   You should see `kubernetes.default.svc.cluster.local` resolving correctly.

## Installing NGINX Ingress Controller via Helm

1. Add the NGINX ingress Helm repository:
   ```bash
   helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
   helm repo update
   ```

2. Install the NGINX ingress controller with the required configurations:
   ```bash
   helm install ingress-nginx ingress-nginx/ingress-nginx \
     --namespace ingress-nginx --create-namespace \
     --set controller.config.enable-real-ip=true \
     --set controller.config.use-forwarded-headers=true
   ```

3. Verify the NGINX ingress controller is running:
   ```bash
   kubectl get pods -n ingress-nginx
   ```

## Installing cert-manager via Helm

1. Add the `cert-manager` Helm repository:
   ```bash
   helm repo add jetstack https://charts.jetstack.io
   helm repo update
   ```

2. Install `cert-manager` using Helm:
   ```bash
   kubectl create namespace cert-manager
   helm install cert-manager jetstack/cert-manager \
     --namespace cert-manager \
     --version v1.12.0 \
     --set installCRDs=true
   ```

3. Verify `cert-manager` is running:
   ```bash
   kubectl get pods -n cert-manager
   ```

## Deploying the Application

1. Apply the namespace and RBAC configuration:
   ```bash
   kubectl apply -f deploy/deploy.yaml
   ```

2. Apply the optional Cloudflare ClusterIssuer configuration (if needed):
   ```bash
   kubectl apply -f deploy/optional-ingress-cert-issuer.yaml
   ```

3. Verify the deployment:
   ```bash
   kubectl get pods -n kube-oidc-issuer-reflector
   ```

4. Access the application:
   - Use the `$OIDC_ISSUER_FQDN` specified in your ingress configuration to access the endpoints:
     - OpenID Configuration: `https://$OIDC_ISSUER_FQDN/.well-known/openid-configuration`
     - JWKS: `https://$OIDC_ISSUER_FQDN/openid/v1/jwks`

## Using the Public Docker Image

Instead of building the Docker image locally, you can use the public image available on GitHub Container Registry:

1. Update the deployment YAML file to use the public image:
   ```yaml
   # filepath: deploy/deploy.yaml
   containers:
     - name: kube-oidc-issuer-reflector
       image: ghcr.io/kangarookube/kube-oidc-issuer-reflector:latest
   ```

2. Apply the updated deployment:
   ```bash
   kubectl apply -f deploy/deploy.yaml
   ```

## Environment Variables

- `DEFAULT_RATE_LIMIT`: Set the rate limit for API requests (e.g., `10 per second`).
- `ALLOWED_USER_AGENT`: Restrict access to specific User-Agent headers.

## Troubleshooting

If you encounter issues, refer to the troubleshooting documentation or check the application logs.

## Contributing

See the CONTRIBUTING.md file for details on how to contribute to this project.