// Step 1 inventory: clean per SAD 6.5 (no output-param write on error path).
CellMonitor::CellMonitor(CellSensor& sensor) : sensor_(sensor) {
}
