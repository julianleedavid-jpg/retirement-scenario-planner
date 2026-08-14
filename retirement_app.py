# Custom HTML/CSS styling with dark text and clean light rows for high contrast
html_table_css = """
<style>
.custom-table-container {
    max-height: 800px;
    overflow-y: auto;
    border: 1px solid rgba(255, 255, 255, 0.15);
    border-radius: 6px;
    margin-bottom: 20px;
}
.custom-table {
    width: 100%;
    border-collapse: collapse;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    font-size: 12px;
}
.custom-table th {
    position: sticky;
    top: 0;
    background-color: #1e222a;
    color: #ffffff;
    padding: 8px 6px;
    text-align: center;
    border-bottom: 2px solid #374151;
    border-right: 1px solid rgba(255, 255, 255, 0.1);
    font-size: 11px;
    font-weight: 600;
    white-space: normal;
    word-wrap: break-word;
    max-width: 90px;
    line-height: 1.25;
}
.custom-table th:last-child {
    border-right: none;
}
.custom-table td {
    padding: 7px 6px;
    text-align: right;
    border-bottom: 1px solid #e5e7eb;
    border-right: 1px solid #e5e7eb;
    background-color: #f9fafb;
    color: #111827; /* Dark slate text for maximum readability */
    font-weight: 600;
    white-space: nowrap;
}
.custom-table td:last-child {
    border-right: none;
}
.custom-table td:first-child, .custom-table td:nth-child(2) {
    text-align: center;
}
.custom-table tr:nth-child(even) td {
    background-color: #f3f4f6; /* Subtle zebra striping */
}
.custom-table tr:hover td {
    background-color: #e5e7eb;
}
</style>
"""
