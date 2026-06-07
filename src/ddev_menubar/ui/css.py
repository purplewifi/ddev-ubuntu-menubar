APP_CSS = b"""
/* Status indicator dots */
.status-dot {
    border-radius: 50%;
    min-width: 8px;
    min-height: 8px;
}
.status-dot.running {
    background-color: #2ecc71;
}
.status-dot.stopped {
    background-color: #8e9399;
}
.status-dot.unhealthy {
    background-color: #e67e22;
}

/* Project list rows */
.project-row {
    padding: 6px 10px;
}
.project-row:selected {
    background-color: alpha(@theme_selected_bg_color, 0.3);
}
.project-name {
    font-weight: bold;
}
.project-path {
    font-size: 0.85em;
    color: alpha(@theme_fg_color, 0.65);
}
.project-url {
    font-size: 0.8em;
    color: alpha(@theme_fg_color, 0.5);
}
.project-status-running {
    color: #2ecc71;
    font-size: 0.85em;
}
.project-status-stopped {
    color: alpha(@theme_fg_color, 0.6);
    font-size: 0.85em;
}

/* Group rows */
.group-row {
    padding: 6px 10px;
}
.group-name {
    font-weight: bold;
}
.group-summary {
    font-size: 0.85em;
    color: alpha(@theme_fg_color, 0.65);
}

/* Status bar */
.status-bar {
    font-size: 0.85em;
    padding: 4px 10px;
}
.status-bar.error {
    color: #e74c3c;
}
.status-bar.info {
    color: alpha(@theme_fg_color, 0.75);
}

/* Startup progress */
.progress-step {
    padding: 3px 0;
}
.progress-step-complete {
    color: #2ecc71;
}
.progress-step-active {
    font-weight: bold;
}
.progress-step-failed {
    color: #e74c3c;
}
.progress-step-pending {
    color: alpha(@theme_fg_color, 0.45);
}

/* Detail labels */
.detail-key {
    font-size: 0.85em;
    color: alpha(@theme_fg_color, 0.65);
    min-width: 110px;
}
.detail-value {
    font-size: 0.85em;
}
.detail-url {
    color: @link_color;
    font-size: 0.85em;
}

/* Footer / toolbar */
.footer-bar {
    padding: 6px 10px;
    border-top: 1px solid alpha(@borders, 0.5);
}

/* Log viewer */
.log-view {
    font-family: monospace;
    font-size: 0.85em;
}

/* mkcert warning banner */
.mkcert-banner {
    background-color: alpha(#e67e22, 0.12);
    border-top: 1px solid alpha(#e67e22, 0.35);
    border-bottom: 1px solid alpha(#e67e22, 0.35);
    padding: 5px 10px;
}
.mkcert-banner-label {
    font-size: 0.85em;
    color: #c0601a;
}

/* Action report */
.hint-row {
    padding: 4px 0;
    color: alpha(@theme_fg_color, 0.8);
    font-size: 0.9em;
}
.excerpt-box {
    background-color: alpha(@theme_bg_color, 0.5);
    padding: 6px;
    border-radius: 4px;
    font-family: monospace;
    font-size: 0.8em;
}
"""
