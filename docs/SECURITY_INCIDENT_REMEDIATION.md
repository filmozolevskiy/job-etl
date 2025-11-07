# Security Incident Remediation Guide

## Incident Summary

**Date**: November 7th, 2025  
**Issue**: SMTP credentials (Gmail App Password) were exposed in `docs/SETUP_EMAIL.md` and committed to GitHub.

**Exposed Credentials**:
- Gmail App Password: `rkxxnzawzpdriwns`
- Email addresses: `filmozolevskiy@gmail.com`, `anderos691@gmail.com`

## Immediate Actions Required

### 1. Revoke the Exposed Gmail App Password ⚠️

**CRITICAL**: Do this immediately to prevent unauthorized access.

1. Go to: https://myaccount.google.com/apppasswords
2. Find the App Password named "Job-ETL" (or similar)
3. Click "Revoke" to delete it
4. Create a new App Password if needed

### 2. Update Local Configuration

After revoking the old password:

1. **If using `.env` file**:
   ```bash
   # Update SMTP_PASSWORD with new App Password
   SMTP_PASSWORD=your-new-app-password
   ```

2. **If using Docker secrets**:
   ```bash
   echo "your-new-app-password" > secrets/notifications/smtp_password.txt
   chmod 600 secrets/notifications/smtp_password.txt
   ```

3. **Restart services**:
   ```bash
   docker-compose restart airflow-webserver airflow-scheduler
   ```

### 3. Remove Credentials from Git History

The credentials are still in git history. To completely remove them:

**Option A: Use git-filter-repo (Recommended)**
```bash
# Install git-filter-repo if needed
pip install git-filter-repo

# Remove the password from all history
git filter-repo --replace-text <(echo "rkxxnzawzpdriwns==>REDACTED")

# Force push (WARNING: This rewrites history)
git push origin --force --all
```

**Option B: Use BFG Repo-Cleaner**
```bash
# Download BFG from https://rtyley.github.io/bfg-repo-cleaner/
java -jar bfg.jar --replace-text passwords.txt
git reflog expire --expire=now --all
git gc --prune=now --aggressive
git push origin --force --all
```

**⚠️ WARNING**: Force pushing rewrites git history. Coordinate with your team first!

### 4. Verify No Other Exposed Secrets

Check for other exposed credentials:
```bash
# Search for potential secrets
grep -r "SMTP_PASSWORD" . --exclude-dir=.git --exclude-dir=__pycache__
grep -r "password.*=" . --exclude-dir=.git --exclude-dir=__pycache__ | grep -v "test"
```

## Prevention Measures

### ✅ Already Implemented

1. **`.gitignore`** properly excludes:
   - `secrets/` directory
   - `.env` files
   - `*.key`, `*.pem` files

2. **Documentation** now uses placeholders instead of real credentials

### 🔒 Best Practices Going Forward

1. **Never commit real credentials** to git, even in documentation
2. **Use placeholders** in examples: `your-password-here`, `your-email@example.com`
3. **Use Docker secrets** or environment variables for production
4. **Review PRs carefully** for exposed secrets before merging
5. **Use secret scanning tools**:
   - GitHub Secret Scanning (already enabled)
   - GitGuardian (already detecting issues)
   - Pre-commit hooks with `detect-secrets`

### Recommended Pre-commit Hook

Add to `.git/hooks/pre-commit`:
```bash
#!/bin/bash
# Check for common secret patterns
if git diff --cached | grep -E "(password|secret|api_key|token)\s*[:=]\s*['\"][^'\"]{8,}" | grep -v "your-.*-here"; then
    echo "ERROR: Potential secret detected in commit!"
    echo "Please remove any real credentials before committing."
    exit 1
fi
```

## Status

- [x] Credentials removed from `docs/SETUP_EMAIL.md`
- [ ] Old App Password revoked
- [ ] New App Password created and configured
- [ ] Git history cleaned (if needed)
- [ ] Services restarted with new credentials

## References

- [GitHub: Removing sensitive data from a repository](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository)
- [Google: Manage App Passwords](https://support.google.com/accounts/answer/185833)

