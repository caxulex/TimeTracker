# Service Level Agreement (SLA)

**[APPLICATION_NAME]**  
**Version:** 1.0  
**Effective Date:** [DATE]

---

## 1. Overview

This Service Level Agreement ("SLA") defines the service commitments for [APPLICATION_NAME] provided by [COMPANY_NAME] ("Provider") to [CLIENT_NAME] ("Client").

This SLA is incorporated into and subject to the terms of the Master Service Agreement or Terms of Service.

---

## 2. Service Tiers

### 2.1 Available Plans

| Feature | Basic | Standard | Premium | Enterprise |
|---------|-------|----------|---------|------------|
| **Monthly Price** | $[X]/user | $[X]/user | $[X]/user | Custom |
| **Uptime SLA** | 99.0% | 99.5% | 99.9% | 99.95% |
| **Support Response** | 72 hours | 24 hours | 4 hours | 1 hour |
| **Support Hours** | Business | Business | 24/5 | 24/7 |
| **Support Channels** | Email | Email, Chat | All | All + Dedicated |
| **Data Backup** | Daily | Daily | Every 6 hours | Real-time |
| **Retention** | 7 days | 30 days | 90 days | Custom |
| **Credits** | None | Yes | Yes | Yes |

---

## 3. Service Availability

### 3.1 Uptime Commitment

Provider commits to the following uptime percentages for the Client's selected tier:

| Tier | Monthly Uptime | Annual Uptime | Max Monthly Downtime |
|------|----------------|---------------|---------------------|
| Basic | 99.0% | 99.0% | 7 hours 18 minutes |
| Standard | 99.5% | 99.5% | 3 hours 39 minutes |
| Premium | 99.9% | 99.9% | 43 minutes 50 seconds |
| Enterprise | 99.95% | 99.95% | 21 minutes 55 seconds |

### 3.2 Measurement Period
Uptime is calculated monthly, from the first to the last day of each calendar month.

### 3.3 Uptime Calculation
```
Uptime % = ((Total Minutes - Downtime Minutes) / Total Minutes) × 100
```

### 3.4 Exclusions
The following are excluded from downtime calculations:

1. **Scheduled Maintenance**: Pre-announced maintenance windows
2. **Emergency Maintenance**: Critical security patches (< 4 hours notice)
3. **Client Actions**: Issues caused by Client's equipment or actions
4. **Force Majeure**: Natural disasters, war, government actions
5. **Third-Party Services**: Failures of third-party providers
6. **Network Issues**: Internet connectivity outside Provider's control

---

## 4. Scheduled Maintenance

### 4.1 Maintenance Windows

| Type | Day | Time (UTC) | Max Duration |
|------|-----|------------|--------------|
| Regular | Sunday | 02:00-06:00 | 4 hours |
| Emergency | Any | Any | As needed |

### 4.2 Notification Requirements

| Maintenance Type | Notice Period |
|-----------------|---------------|
| Major Updates | 7 days |
| Minor Updates | 48 hours |
| Emergency Patches | Best effort |

### 4.3 Communication Channels
Maintenance notifications will be sent via:
- Email to registered administrators
- Status page updates at [STATUS_PAGE_URL]
- In-app notifications (when possible)

---

## 5. Support Services

### 5.1 Issue Priority Levels

| Priority | Definition | Examples |
|----------|------------|----------|
| **P1 - Critical** | Service completely unavailable | Total outage, data loss |
| **P2 - High** | Major feature unavailable | Cannot log time, reports broken |
| **P3 - Medium** | Feature partially impaired | Slow performance, UI issues |
| **P4 - Low** | Minor issue or question | Feature request, how-to |

### 5.2 Response Time Targets

| Priority | Basic | Standard | Premium | Enterprise |
|----------|-------|----------|---------|------------|
| P1 | 72 hours | 4 hours | 1 hour | 15 minutes |
| P2 | 72 hours | 8 hours | 2 hours | 1 hour |
| P3 | 72 hours | 24 hours | 8 hours | 4 hours |
| P4 | 72 hours | 72 hours | 24 hours | 8 hours |

*Response time = time to initial human response, not resolution*

### 5.3 Resolution Time Targets

| Priority | Target Resolution |
|----------|-------------------|
| P1 | 4 hours |
| P2 | 8 hours |
| P3 | 3 business days |
| P4 | 5 business days |

### 5.4 Support Channels

| Channel | Availability | Best For |
|---------|--------------|----------|
| **Email** | 24/7 submission | Non-urgent issues |
| **Help Desk** | 24/7 submission | All issues |
| **Live Chat** | Business hours | Quick questions |
| **Phone** | Premium/Enterprise | Urgent issues |
| **Dedicated Manager** | Enterprise only | Strategic issues |

### 5.5 Support Contact Information

- **Email**: [SUPPORT_EMAIL]
- **Help Desk**: [HELPDESK_URL]
- **Phone**: [SUPPORT_PHONE] (Premium/Enterprise)
- **Status Page**: [STATUS_PAGE_URL]

---

## 6. Service Credits

### 6.1 Credit Eligibility
Service credits are available for Standard, Premium, and Enterprise tiers when uptime falls below committed levels.

### 6.2 Credit Schedule

| Monthly Uptime | Credit (% of Monthly Fee) |
|----------------|---------------------------|
| 99.0% - 99.49% | 10% |
| 98.0% - 98.99% | 25% |
| 95.0% - 97.99% | 50% |
| < 95.0% | 100% |

### 6.3 Credit Request Process

1. Submit request within 30 days of the incident
2. Include: dates, times, and description of outage
3. Request via email to [SUPPORT_EMAIL]
4. Credits applied to next billing cycle

### 6.4 Credit Limitations

- Maximum credit: 100% of monthly fee
- Credits are non-transferable and non-cashable
- Credits do not apply to one-time fees
- Credits void if Client is in breach of terms

---

## 7. Data Protection

### 7.1 Backup Schedule

| Tier | Frequency | Retention |
|------|-----------|-----------|
| Basic | Daily | 7 days |
| Standard | Daily | 30 days |
| Premium | Every 6 hours | 90 days |
| Enterprise | Real-time | Custom |

### 7.2 Recovery Objectives

| Metric | Target |
|--------|--------|
| **RPO** (Recovery Point Objective) | ≤ 24 hours (varies by tier) |
| **RTO** (Recovery Time Objective) | ≤ 4 hours |

### 7.3 Data Location
Primary data storage: [DATA_CENTER_LOCATION]  
Backup storage: [BACKUP_LOCATION]

---

## 8. Security Commitments

### 8.1 Security Measures

- TLS 1.3 encryption in transit
- AES-256 encryption at rest
- Regular security audits
- Vulnerability scanning
- Access logging and monitoring

### 8.2 Compliance
Provider maintains compliance with:
- [ ] SOC 2 Type II
- [ ] ISO 27001
- [ ] GDPR
- [ ] HIPAA (if applicable)

### 8.3 Incident Response

| Severity | Notification | Investigation |
|----------|--------------|---------------|
| Critical | Within 4 hours | Immediate |
| High | Within 24 hours | Within 48 hours |
| Medium | Within 72 hours | Within 5 days |

---

## 9. Reporting

### 9.1 Standard Reports

Provider will make available:
- Monthly uptime reports
- Support ticket summaries
- Usage statistics

### 9.2 Enterprise Reporting

Enterprise clients receive:
- Quarterly business reviews
- Custom report generation
- Dedicated account management

---

## 10. Escalation Process

### 10.1 Escalation Path

| Level | Contact | Response Time |
|-------|---------|---------------|
| 1 | Support Team | Per SLA |
| 2 | Support Manager | 2 hours |
| 3 | Director of Operations | 4 hours |
| 4 | Executive Leadership | 8 hours |

### 10.2 Escalation Contact

- **Level 2**: [SUPPORT_MANAGER_EMAIL]
- **Level 3**: [OPERATIONS_EMAIL]
- **Level 4**: [EXECUTIVE_EMAIL]

---

## 11. Client Responsibilities

Client agrees to:

1. **Maintain Current Contact Information**: Keep emergency contacts updated
2. **Report Issues Promptly**: Notify Provider of issues immediately
3. **Provide Access**: Grant necessary access for troubleshooting
4. **Follow Procedures**: Use documented support channels
5. **Cooperate**: Work with Provider to resolve issues
6. **System Requirements**: Maintain supported browsers/systems

---

## 12. Term and Amendments

### 12.1 Term
This SLA is effective for the duration of the service agreement.

### 12.2 Amendments
Provider may update this SLA with 30 days notice. Material changes reducing service levels will not apply to existing contracts until renewal.

### 12.3 Review
This SLA will be reviewed annually and updated as necessary.

---

## 13. Definitions

| Term | Definition |
|------|------------|
| **Downtime** | Period when the Service is not operational |
| **Business Hours** | Monday-Friday, 9 AM - 5 PM [TIMEZONE] |
| **Response Time** | Time from issue submission to initial response |
| **Resolution Time** | Time from issue submission to complete resolution |
| **Monthly Fee** | Regular monthly subscription amount |

---

## 14. Contact Information

**[COMPANY_NAME]**  
[ADDRESS]  
[CITY, STATE/PROVINCE, POSTAL CODE]  
[COUNTRY]

**Support**: [SUPPORT_EMAIL]  
**Sales**: [SALES_EMAIL]  
**Phone**: [PHONE_NUMBER]

---

## Agreement

**Provider:**  
[COMPANY_NAME]  
Signature: ______________________  
Name: ______________________  
Title: ______________________  
Date: ______________________

**Client:**  
[CLIENT_NAME]  
Signature: ______________________  
Name: ______________________  
Title: ______________________  
Date: ______________________

---

*Document Version: 1.0*  
*Last Updated: [DATE]*
