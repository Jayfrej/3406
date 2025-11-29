# CSS File Splitter
$css = Get-Content "static\style.css" -Raw
# Split markers (line numbers are approximate, we'll use pattern matching)
$baseEnd = $css.IndexOf("body{")
$layoutEnd = $css.IndexOf("/* Page Content */")
$componentsEnd = $css.IndexOf("/* Toast Notifications */")
$toastEnd = $css.IndexOf("/* Modal */")
$modalsEnd = $css.IndexOf("/* Two Column Layout */")
Write-Host "File size: $($css.Length) characters"
Write-Host "Markers found at positions: $baseEnd, $layoutEnd, $componentsEnd"
