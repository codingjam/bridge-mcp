# Dashboard Features Specification

This document details the specific features and components for each page of the MCP Gateway Dashboard.

## 🏠 Overview Dashboard (Landing Page)

### Layout
```
┌─────────────────────────────────────────────────────────┐
│ 📊 System Status Alert                                 │
├─────────────────────────────────────────────────────────┤
│ [📈 Metrics] [🔧 Services] [⚡ Rate Lim] [👥 Users]    │
├─────────────────────────────────────────────────────────┤
│ [📊 Request Metrics Chart    ] [🟢 Service Health]     │
│                               [🟡 Health Status  ]     │
│                               [🔴 Down Services  ]     │
├─────────────────────────────────────────────────────────┤
│ 📝 Recent Activity Table                               │
└─────────────────────────────────────────────────────────┘
```

### Components

#### **System Status Alert**
- Green: "All systems operational"
- Yellow: "Some services degraded" 
- Red: "Critical issues detected"
- Auto-updates every 30 seconds

#### **Metrics Cards (4 cards)**
1. **Active Services** - Count with trend indicator
2. **Rate Limit Usage** - Percentage with visual gauge
3. **Active Users** - Current user count
4. **Avg Response Time** - Milliseconds with trend

#### **Request Metrics Chart**
- Line chart showing requests/minute over last 24 hours
- Multiple lines: Total, Success, Errors
- Interactive tooltips with detailed data

#### **Service Health Grid**
- Visual grid of all services with status indicators
- Click to view service details
- Color-coded: Green (healthy), Yellow (degraded), Red (down)

#### **Recent Activity Table**
- Last 20 requests/events
- Columns: Time, User, Service, Action, Status, Response Time
- Real-time updates via WebSocket

---

## 🔧 Services Management

### Layout
```
┌─────────────────────────────────────────────────────────┐
│ Services (12) [+ Add Service] [🔄 Refresh] [⚙️ Config] │
├─────────────────────────────────────────────────────────┤
│ 🔍 Search: [__________] Status: [All ▼] Type: [All ▼]  │
├─────────────────────────────────────────────────────────┤
│ ┌─ Service Name ─┬─ Status ─┬─ Health ─┬─ Actions ─┐   │
│ │ 🟢 Service A   │ Active   │ Healthy  │ [⚙️][🧪][📊] │
│ │ 🟡 Service B   │ Active   │ Degraded │ [⚙️][🧪][📊] │
│ │ 🔴 Service C   │ Disabled │ Down     │ [⚙️][🧪][📊] │
│ └──────────────┴─────────┴─────────┴──────────────┘   │
└─────────────────────────────────────────────────────────┘
```

### Components

#### **Services Table**
- **Columns:**
  - Name + Icon (status indicator)
  - Status (Active/Disabled toggle)
  - Health (Healthy/Degraded/Down with response time)
  - Transport (HTTP/stdio)
  - Last Check (timestamp)
  - Actions (Configure, Test, View Logs, Delete)

#### **Add/Edit Service Modal**
```
┌─────────────────────────────────────┐
│ ✨ Add New Service                  │
├─────────────────────────────────────┤
│ Service Name: [________________]    │
│ Description:  [________________]    │
│ Transport:    [HTTP ▼]             │
│ Endpoint:     [________________]    │
│ Enabled:      [✓] Enable service   │
│ Timeout:      [30] seconds         │
│ Tags:         [tag1, tag2]         │
├─────────────────────────────────────┤
│              [Cancel] [Save Service] │
└─────────────────────────────────────┘
```

#### **Service Details Modal**
- Service configuration display
- Health metrics and response times
- Recent requests/errors
- Configuration export/import

#### **Service Actions**
- **Test Connection:** Ping service and show response
- **View Logs:** Filter logs for specific service
- **Enable/Disable:** Toggle service availability
- **Delete:** Remove service with confirmation

---

## 🔐 Authentication Dashboard

### Layout
```
┌─────────────────────────────────────────────────────────┐
│ Authentication Status                                    │
├─────────────────────────────────────────────────────────┤
│ [OIDC Status] [Active Sessions] [Token Info] [Logs]     │
├─────────────────────────────────────────────────────────┤
│ 🔐 OIDC Configuration                                   │
│ Provider: Keycloak                                       │
│ Status: ✅ Connected                                     │
│ Realm: master                                           │
│ Client ID: mcp-gateway                                  │
├─────────────────────────────────────────────────────────┤
│ 👥 Active Sessions (23)                                │
│ ┌─ User ────────┬─ Session ─┬─ Expires ─┬─ Actions ─┐  │
│ │ john.doe      │ 2h 15m    │ 6h 45m    │ [🚪][📊] │  │
│ │ jane.smith    │ 45m       │ 7h 15m    │ [🚪][📊] │  │
│ └──────────────┴──────────┴──────────┴───────────┘  │
└─────────────────────────────────────────────────────────┘
```

### Components

#### **OIDC Configuration Card**
- Provider status and connection health
- Configuration summary (realm, client ID, etc.)
- Last successful token validation
- Error states with troubleshooting links

#### **Active Sessions Table**
- Current authenticated users
- Session duration and expiration
- Actions: Revoke session, View details
- Real-time updates

#### **Token Information Panel**
- Current user's JWT claims
- Token expiration countdown
- Scopes and permissions
- Refresh token status

#### **Authentication Logs**
- Login/logout events
- Token validation attempts
- Failed authentication attempts
- Filterable by user, time range, event type

---

## ⚡ Rate Limiting Dashboard

### Layout
```
┌─────────────────────────────────────────────────────────┐
│ Rate Limiting Overview                                   │
├─────────────────────────────────────────────────────────┤
│ [📊 Usage] [⚙️ Config] [🚫 Blocked] [📈 Trends]        │
├─────────────────────────────────────────────────────────┤
│ ⚡ Current Usage                   🔧 Configuration      │
│ ┌─────────────────────────────┐   ┌─────────────────────┐ │
│ │ User: john.doe              │   │ Default Limit: 5/min│ │
│ │ Service: mcp-server-1       │   │ Window: 60 seconds  │ │
│ │ Usage: ████████░░ 4/5       │   │ Backend: Memory     │ │
│ │ Resets in: 45 seconds       │   │ [Edit Configuration]│ │
│ └─────────────────────────────┘   └─────────────────────┘ │
├─────────────────────────────────────────────────────────┤
│ 📊 Usage Trends (Last 24h)                             │
│ [Line chart showing rate limit usage over time]         │
└─────────────────────────────────────────────────────────┘
```

### Components

#### **Usage Overview Cards**
- Top rate-limited users/services
- Current usage vs limits
- Reset timers and countdowns
- Real-time usage updates

#### **Configuration Panel**
- Default rate limits (requests per minute)
- Window duration settings
- Backend configuration (Memory/Redis)
- Per-service overrides

#### **Blocked Requests Log**
- Table of rate-limited requests
- Columns: Time, User, Service, Tool, Limit Exceeded
- Filter by user, service, time range

#### **Usage Trends Chart**
- Historical rate limit usage
- Peak usage times identification
- Trend analysis for capacity planning

---

## 📝 Logs Viewer

### Layout
```
┌─────────────────────────────────────────────────────────┐
│ System Logs                                              │
├─────────────────────────────────────────────────────────┤
│ 🔍 [Search logs...] Level:[All▼] Service:[All▼] [Export]│
├─────────────────────────────────────────────────────────┤
│ [🔴 Live] Auto-scroll: [✓] Last 1000 entries            │
├─────────────────────────────────────────────────────────┤
│ ┌─ Time ──┬─ Level ─┬─ Service ─┬─ Message ───────────┐ │
│ │ 14:23:45 │ INFO    │ gateway   │ Request processed   │ │
│ │ 14:23:44 │ WARN    │ auth      │ Token near expiry   │ │
│ │ 14:23:43 │ ERROR   │ service-a │ Connection failed   │ │
│ └─────────┴────────┴──────────┴───────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

### Components

#### **Log Filters**
- Text search across log messages
- Filter by log level (DEBUG, INFO, WARN, ERROR)
- Filter by service/component
- Time range selector

#### **Real-time Log Stream**
- WebSocket connection for live logs
- Auto-scroll toggle
- Pause/resume stream
- Color-coded log levels

#### **Log Entry Details**
- Expandable log entries for full details
- Correlation ID linking
- Stack traces for errors
- JSON formatting for structured logs

#### **Log Export**
- Export filtered logs as CSV/JSON
- Date range selection
- Email export option

---

## ⚙️ Configuration Management

### Layout
```
┌─────────────────────────────────────────────────────────┐
│ Gateway Configuration                                    │
├─────────────────────────────────────────────────────────┤
│ [🔧 Settings] [🎛️ Features] [📋 Environment] [📜 History]│
├─────────────────────────────────────────────────────────┤
│ 🔧 Core Settings                                        │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Host: [127.0.0.1    ] Port: [8000]                 │ │
│ │ Debug Mode: [☐] Enable debug logging               │ │
│ │ Log Level: [INFO ▼]                                │ │
│ │ Log Format: [JSON ▼]                               │ │
│ └─────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────┤
│ 🎛️ Feature Toggles                                     │
│ │ Authentication: [✓] OIDC enabled                    │ │
│ │ Rate Limiting:  [✓] 5 requests/minute              │ │
│ │ Audit Logging:  [✓] Full request logging           │ │
│ └─────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

### Components

#### **Core Settings Form**
- Server configuration (host, port)
- Logging configuration
- Security settings
- Form validation and error handling

#### **Feature Toggles**
- Enable/disable authentication
- Enable/disable rate limiting
- Enable/disable audit logging
- Real-time status indicators

#### **Environment Information**
- Current environment variables
- System information
- Version information
- Health check status

#### **Configuration History**
- Track configuration changes
- Rollback capability
- Change approval workflow
- Audit trail for compliance

---

## 🎨 UI Components Library

### **Common Components**

#### **StatusBadge**
```tsx
<StatusBadge status="healthy" />    // Green dot + "Healthy"
<StatusBadge status="degraded" />   // Yellow dot + "Degraded"  
<StatusBadge status="down" />       // Red dot + "Down"
```

#### **MetricCard**
```tsx
<MetricCard
  title="Active Services"
  value={12}
  trend="+2.5%"
  icon={<ServerIcon />}
/>
```

#### **ActionButton**
```tsx
<ActionButton icon={<SettingsIcon />} onClick={onConfigure}>
  Configure
</ActionButton>
```

#### **LoadingState**
```tsx
<LoadingState message="Loading services..." />
```

#### **EmptyState**
```tsx
<EmptyState 
  title="No services found"
  description="Add your first MCP service to get started"
  action={<Button>Add Service</Button>}
/>
```

---

## 📱 Responsive Behavior

### **Desktop (1024px+)**
- Full sidebar navigation
- Multi-column layouts
- Detailed tables with all columns

### **Tablet (768-1023px)**
- Collapsible sidebar
- Adapted grid layouts
- Essential table columns only

### **Mobile (320-767px)**
- Hidden sidebar with overlay
- Single column layouts
- Card-based service list
- Touch-friendly interactions

---

This specification provides the detailed blueprint for building a clean, professional, and functional MCP Gateway Dashboard that focuses on essential features without over-engineering.
