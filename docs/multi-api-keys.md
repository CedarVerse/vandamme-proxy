# Multi-API Key Support

Configure multiple API keys per provider with automatic round-robin rotation and intelligent failover for production-ready resilience.

## Overview

The multi-API key feature enhances Vandamme Proxy's reliability and scalability by:

- **Load Distribution**: Distribute requests across multiple API keys
- **Automatic Failover**: Seamless rotation on authentication failures
- **Rate Limit Management**: Avoid hitting single-key rate limits
- **High Availability**: Continue serving requests even when some keys fail

## Configuration

### Basic Setup

Configure multiple API keys using whitespace separation:

```bash
# Single API key (traditional, still supported)
OPENAI_API_KEY="sk-your-single-key"

# Multiple API keys for load balancing and failover
OPENAI_API_KEY="sk-key1 sk-key2 sk-key3"

# Multiple keys for different providers
ANTHROPIC_API_KEY="sk-ant-key1 sk-ant-key2 sk-ant-backup"
POE_API_KEY="poe-key-1 poe-key-2"
AZURE_API_KEY="azure-key-1 azure-key-2"
```

### Key Selection Behavior

1. **Round-Robin Rotation**: Keys are selected in rotation order
2. **Process-Global State**: Rotation state is shared across all requests
3. **Thread-Safe**: Uses asyncio locks for concurrent request safety
4. **Per-Provider Tracking**: Each provider maintains independent rotation state

### Automatic Failover

The system automatically rotates to the next key when:

- HTTP 401 (Unauthorized)
- HTTP 403 (Forbidden)
- HTTP 429 (Rate Limited)
- Error messages containing "insufficient_quota"

The proxy attempts all configured keys before returning an error to the client.

## Advanced Configuration

### Production Deployment Example

```bash
# Production-ready configuration with multiple keys per provider
OPENAI_API_KEY="sk-proj-key1 sk-proj-key2 sk-proj-key3"
ANTHROPIC_API_KEY="sk-ant-prod1 sk-ant-prod2 sk-ant-backup"

# Configure provider-specific settings
OPENAI_BASE_URL="https://api.openai.com/v1"
ANTHROPIC_BASE_URL="https://api.anthropic.com"

# Set default provider
VDM_DEFAULT_PROVIDER="openai"
```

### Cost Optimization Strategy

Use different providers for different use cases:

```bash
# Expensive provider for critical tasks
OPENAI_API_KEY="sk-gpt4-key1 sk-gpt4-key2"

# Cheaper provider for bulk operations
POE_API_KEY="poe-bulk-key1 poe-bulk-key2 poe-bulk-key3"

# Local models for development
OLLAMA_API_KEY="dummy-key"
OLLAMA_BASE_URL="http://localhost:11434/v1"
```

### Mixed Static and Passthrough

You can combine static multi-key configuration with passthrough mode:

```bash
# Static keys with automatic rotation (recommended for production)
OPENAI_API_KEY="sk-key1 sk-key2 sk-key3"

# Passthrough mode for client-provided keys
POE_API_KEY=!PASSTHRU

# Note: Cannot mix static keys with !PASSTHRU for the same provider
# INVALID: ANTHROPIC_API_KEY="!PASSTHRU sk-ant-key"  # This will raise an error
```

## Monitoring and Debugging

### Request Metrics

Enable request metrics to monitor key rotation:

```bash
LOG_LEVEL=DEBUG
```

The logs will show:
- API key hashes (first 8 characters)
- Which key was used for each request
- When rotation occurs
- Authentication failure details

### Health Checks

Monitor key health using the health endpoint:

```bash
curl http://localhost:8082/health
```

### Key Rotation Debugging

To verify rotation is working:

1. Check logs for key hash changes
2. Monitor for authentication failures
3. Verify request distribution across keys

## Best Practices

### Key Management

1. **Unique Keys**: Use completely independent API keys
2. **Equal Quotas**: Ensure keys have similar rate limits
3. **Regular Rotation**: Periodically rotate keys for security
4. **Backup Keys**: Keep spare keys for emergencies

### Performance Optimization

1. **Balance Load**: Distribute keys evenly across providers
2. **Monitor Usage**: Track per-key usage patterns
3. **Adjust Distribution**: Add/remove keys based on demand

### Security Considerations

1. **Environment Variables**: Store keys securely in environment
2. **Access Control**: Limit access to key configuration
3. **Audit Trails**: Monitor key usage and rotation
4. **Key Revocation**: Quickly revoke compromised keys

## Troubleshooting

### Common Issues

#### All Keys Exhausted
```
HTTP 429: All provider API keys exhausted
```

**Solution**: Check if all keys are valid or temporarily rate-limited.

#### Mixed Configuration Error
```
Configuration Error: Cannot mix !PASSTHRU with static keys
```

**Solution**: Use either all static keys or `!PASSTHRU`, not both.

#### Empty Key Detection
```
Configuration Error: Empty API key detected
```

**Solution**: Ensure no empty strings in your key list.

### Debugging Steps

1. **Check Configuration**:
   ```bash
   env | grep API_KEY
   ```

2. **Verify Key Format**:
   - Ensure proper whitespace separation
   - Check for trailing spaces
   - Validate key formats

3. **Monitor Logs**:
   ```bash
   vdm server start 2>&1 | grep -E "(API KEY|rotation|exhausted)"
   ```

4. **Test Individual Keys**:
   Temporarily use single keys to isolate issues

## Integration Examples

### With Claude Code

```bash
# Configure multiple keys
export OPENAI_API_KEY="sk-key1 sk-key2 sk-key3"

# Start proxy
vdm server start

# Use with Claude Code
ANTHROPIC_BASE_URL=http://localhost:8082 claude --model openai:gpt-4o "Test message"
```

### With Docker Compose

```yaml
version: '3.8'
services:
  vandamme-proxy:
    image: cedarverse/vandamme-proxy:latest
    environment:
      - OPENAI_API_KEY=sk-key1 sk-key2 sk-key3
      - ANTHROPIC_API_KEY=sk-ant-key1 sk-ant-key2
      - LOG_LEVEL=INFO
    ports:
      - "8082:8082"
```

### With Kubernetes

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: api-keys
stringData:
  openai-keys: "sk-key1 sk-key2 sk-key3"
  anthropic-keys: "sk-ant-key1 sk-ant-key2"
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: vandamme-proxy
spec:
  template:
    spec:
      containers:
      - name: proxy
        image: cedarverse/vandamme-proxy:latest
        env:
        - name: OPENAI_API_KEY
          valueFrom:
            secretKeyRef:
              name: api-keys
              key: openai-keys
```

## Limitations

1. **Passthrough Mode**: Only single passthrough key supported (`!PASSTHRU`)
2. **Mixed Mode**: Cannot combine static keys with passthrough for same provider
3. **Key Order**: Rotation follows configured order, not priority
4. **State Persistence**: Rotation state resets on proxy restart

## Future Enhancements

Planned improvements for multi-API key support:

- Weighted round-robin (prioritize faster/cheaper keys)
- Health-based routing (avoid failing keys)
- Persistent rotation state across restarts
- Per-key usage metrics and quotas
- Automatic key health checks