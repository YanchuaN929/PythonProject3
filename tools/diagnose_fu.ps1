# FU diagnostic probe. Copy this ONE file next to the application EXE.
# Run: powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\diagnose_fu.ps1
# No administrator, Python, Office, downloads or application startup required.
# Source workbooks/configuration/databases are never opened for writing.
[CmdletBinding()]
param(
    [string]$ExeDir = '',
    [string]$DataFolder = '',
    [string]$ProfileDir = '',
    [int]$TimeoutSeconds = 180,
    [int]$MaxFuFiles = 30,
    [switch]$SkipRegistry,
    [switch]$ProbeWorker,
    [string]$ReportDir = '',
    [string]$PrivateDir = ''
)

$ErrorActionPreference = 'Stop'
$scriptPath = $MyInvocation.MyCommand.Path
if (-not $ExeDir) { $ExeDir = Split-Path -Parent $scriptPath }
$ExeDir = [IO.Path]::GetFullPath($ExeDir)
if (-not $ProfileDir) { $ProfileDir = Join-Path $env:USERPROFILE '.excel_processor' }
$TimeoutSeconds = [Math]::Max(15, [Math]::Min(600, $TimeoutSeconds))
$MaxFuFiles = [Math]::Max(1, [Math]::Min(100, $MaxFuFiles))

function Get-PeMachine([string]$Path) {
    $s = $null; $b = $null
    try {
        $s = [IO.File]::Open($Path, 'Open', 'Read', 'ReadWrite')
        $b = New-Object IO.BinaryReader($s)
        if ($b.ReadUInt16() -ne 0x5a4d) { return 0 }
        $s.Position = 60; $offset = $b.ReadInt32(); $s.Position = $offset
        if ($b.ReadUInt32() -ne 0x4550) { return 0 }
        return [int]$b.ReadUInt16()
    } catch { return 0 } finally { if ($b) { $b.Close() } elseif ($s) { $s.Close() } }
}

function Quote-Argument([string]$Value) {
    if ($Value.Contains('"')) { throw 'A path argument contains an invalid quote.' }
    return '"' + [regex]::Replace($Value, '(\\+)$', '$1$1') + '"'
}

# A bounded child process keeps a stalled SMB read from hanging the launcher.
# The child writes checkpoints; on timeout, the partial report is retained.
if (-not $ProbeWorker) {
    $stamp = (Get-Date -Format 'yyyyMMdd_HHmmss') + '_' + [Guid]::NewGuid().ToString('N').Substring(0, 8)
    $name = 'FU_Diagnostic_' + $stamp
    try { $ReportDir = (New-Item -ItemType Directory -Path (Join-Path $ExeDir $name)).FullName }
    catch { $ReportDir = (New-Item -ItemType Directory -Path (Join-Path ([IO.Path]::GetTempPath()) $name)).FullName }
    $PrivateDir = Join-Path ([IO.Path]::GetTempPath()) ('FU_Probe_Private_' + [Guid]::NewGuid().ToString('N'))
    [void][IO.Directory]::CreateDirectory($PrivateDir)
    $child = $null
    try {
        $dll = Join-Path $ExeDir '_internal\sqlite3.dll'
        if (-not [IO.File]::Exists($dll)) { $dll = Join-Path $ExeDir 'sqlite3.dll' }
        $machine = Get-PeMachine $dll
        $hostExe = Join-Path $PSHOME 'powershell.exe'
        if (-not [IO.File]::Exists($hostExe)) { $hostExe = Join-Path $env:WINDIR 'System32\WindowsPowerShell\v1.0\powershell.exe' }
        if ($machine -eq 0x14c -and [IntPtr]::Size -eq 8) {
            $hostExe = Join-Path $env:WINDIR 'SysWOW64\WindowsPowerShell\v1.0\powershell.exe'
        } elseif ($machine -eq 0x8664 -and [IntPtr]::Size -eq 4 -and $env:PROCESSOR_ARCHITEW6432) {
            $hostExe = Join-Path $env:WINDIR 'Sysnative\WindowsPowerShell\v1.0\powershell.exe'
        }
        $arguments = '-NoProfile -NonInteractive -ExecutionPolicy Bypass -File ' + (Quote-Argument $scriptPath) + ' -ProbeWorker'
        foreach ($pair in @(@('ExeDir', $ExeDir), @('DataFolder', $DataFolder), @('ProfileDir', $ProfileDir), @('ReportDir', $ReportDir), @('PrivateDir', $PrivateDir))) {
            if ($pair[1]) { $arguments += ' -' + $pair[0] + ' ' + (Quote-Argument $pair[1]) }
        }
        $arguments += ' -MaxFuFiles ' + $MaxFuFiles
        if ($SkipRegistry) { $arguments += ' -SkipRegistry' }
        $info = New-Object Diagnostics.ProcessStartInfo
        $info.FileName = $hostExe; $info.Arguments = $arguments
        $info.UseShellExecute = $false; $info.CreateNoWindow = $true
        $info.WindowStyle = [Diagnostics.ProcessWindowStyle]::Hidden
        $info.WorkingDirectory = $ExeDir
        Write-Host 'Read-only FU diagnostic started. No business data will be changed.'
        Write-Host ('Report: ' + $ReportDir)
        $child = [Diagnostics.Process]::Start($info)
        $timer = [Diagnostics.Stopwatch]::StartNew(); $lastProgress = ''
        while (-not $child.WaitForExit(500)) {
            $progressPath = Join-Path $ReportDir 'progress.txt'
            if ([IO.File]::Exists($progressPath)) {
                try { $progress = [IO.File]::ReadAllText($progressPath); if ($progress -ne $lastProgress) { Write-Host $progress; $lastProgress = $progress } } catch {}
            }
            if ($timer.Elapsed.TotalSeconds -gt $TimeoutSeconds) {
                $child.Kill(); $child.WaitForExit()
                [IO.File]::WriteAllText((Join-Path $ReportDir 'TIMEOUT.txt'), 'Probe timed out. Partial report retained. Last phase: ' + $lastProgress, [Text.Encoding]::UTF8)
                break
            }
        }
        Write-Host ('Finished. Send the files in: ' + $ReportDir)
        Write-Host 'Logs may contain account names and internal paths. Review before sharing.'
        if ($child.ExitCode -ne 0 -and -not [IO.File]::Exists((Join-Path $ReportDir 'TIMEOUT.txt'))) {
            [IO.File]::WriteAllText((Join-Path $ReportDir 'WORKER_EXIT.txt'), 'Worker exit code: ' + $child.ExitCode + '. Check script policy / endpoint protection if no report was created.', [Text.Encoding]::UTF8)
        }
    } finally {
        if ($child -and -not $child.HasExited) { $child.Kill(); $child.WaitForExit() }
        if ($child) { $child.Dispose() }
        # Only exact files under this run's generated private directory may be removed.
        $tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\') + '\'
        $privateFull = [IO.Path]::GetFullPath($PrivateDir)
        if ($privateFull.StartsWith($tempRoot, [StringComparison]::OrdinalIgnoreCase) -and (Split-Path $privateFull -Leaf) -match '^FU_Probe_Private_[0-9a-f]{32}$') {
            foreach ($leaf in @('registry.db', 'registry.db-wal', 'registry.db-shm', 'registry.db-journal')) {
                $target = Join-Path $privateFull $leaf
                if ([IO.File]::Exists($target)) { [IO.File]::Delete($target) }
            }
            if ([IO.Directory]::Exists($privateFull)) { [IO.Directory]::Delete($privateFull, $false) }
        }
    }
    return
}

# C# uses .NET's legacy DeflateStream instead of ZipArchive (absent on older Win7).
# It reads physical cells, not the worksheet's possibly bogus declared dimension.
$supportSource = @'
using System;
using System.IO;
using System.IO.Compression;
using System.Xml;
using System.Text;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Diagnostics;
public static class FuProbe {
    public static string Tail(string path, int maxBytes) {
        using (FileStream f = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite)) {
            long start = Math.Max(0, f.Length - maxBytes); f.Position = start;
            using (StreamReader r = new StreamReader(f, Encoding.UTF8, true)) {
                if (start > 0) r.ReadLine(); return r.ReadToEnd();
            }
        }
    }
    class Zip : IDisposable {
        FileStream file; BinaryReader reader;
        public Dictionary<string, long[]> Entries = new Dictionary<string, long[]>();
        public Zip(string path) {
            try {
                file = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite);
                reader = new BinaryReader(file); long begin = Math.Max(0, file.Length - 65557);
                file.Position = begin; byte[] tail = reader.ReadBytes((int)(file.Length - begin)); int eocd = -1;
                for (int i = tail.Length - 22; i >= 0; i--) {
                    if (BitConverter.ToUInt32(tail, i) == 0x06054b50 && i + 22 + BitConverter.ToUInt16(tail, i + 20) == tail.Length) { eocd = i; break; }
                }
                if (eocd < 0) throw new InvalidDataException("Not a supported ZIP workbook");
                int count = BitConverter.ToUInt16(tail, eocd + 10); uint offset = BitConverter.ToUInt32(tail, eocd + 16);
                if (count == 65535 || offset == UInt32.MaxValue) throw new NotSupportedException("ZIP64 probe unsupported; not evidence of application failure");
                file.Position = offset;
                for (int i = 0; i < count; i++) {
                    byte[] h = reader.ReadBytes(46);
                    if (h.Length != 46 || BitConverter.ToUInt32(h, 0) != 0x02014b50) throw new InvalidDataException("Invalid ZIP directory");
                    int nl = BitConverter.ToUInt16(h, 28), el = BitConverter.ToUInt16(h, 30), cl = BitConverter.ToUInt16(h, 32);
                    string name = Encoding.UTF8.GetString(reader.ReadBytes(nl));
                    Entries[name] = new long[] { BitConverter.ToUInt32(h, 42), BitConverter.ToUInt32(h, 20), BitConverter.ToUInt32(h, 24), BitConverter.ToUInt16(h, 10), BitConverter.ToUInt16(h, 8) };
                    file.Position += el + cl;
                }
            } catch { Dispose(); throw; }
        }
        public Stream Open(string name) {
            long[] e;
            if (!Entries.TryGetValue(name, out e)) throw new InvalidDataException("Missing ZIP member: " + name);
            if ((e[4] & 1) != 0 || e[1] > 67108864 || e[2] > 268435456) throw new NotSupportedException("Encrypted/oversized ZIP entry");
            file.Position = e[0]; byte[] h = reader.ReadBytes(30);
            if (h.Length != 30 || BitConverter.ToUInt32(h, 0) != 0x04034b50) throw new InvalidDataException("Invalid ZIP local header");
            file.Position += BitConverter.ToUInt16(h, 26) + BitConverter.ToUInt16(h, 28);
            byte[] compressed = reader.ReadBytes((int)e[1]); if (compressed.Length != e[1]) throw new EndOfStreamException();
            MemoryStream input = new MemoryStream(compressed, false);
            if (e[3] == 0) return input;
            if (e[3] == 8) return new DeflateStream(input, CompressionMode.Decompress);
            input.Close(); throw new NotSupportedException("ZIP compression method " + e[3]);
        }
        public void Dispose() { if (reader != null) reader.Close(); else if (file != null) file.Close(); }
    }
    static XmlReader Xml(Stream s) {
        // ProhibitDtd is needed for CLR 2 on Win7 / PowerShell 2.
#pragma warning disable 0618
        XmlReaderSettings settings = new XmlReaderSettings(); settings.ProhibitDtd = true; settings.XmlResolver = null; settings.CloseInput = true;
#pragma warning restore 0618
        return XmlReader.Create(s, settings);
    }
    static XmlDocument Document(Zip zip, string member) {
        XmlDocument d = new XmlDocument(); d.XmlResolver = null;
        using (XmlReader r = Xml(zip.Open(member))) d.Load(r); return d;
    }
    static string TextNodes(XmlNode n) {
        StringBuilder b = new StringBuilder(); foreach (XmlNode t in n.SelectNodes(".//*[local-name()='t' and not(ancestor::*[local-name()='rPh'])]")) b.Append(t.InnerText); return b.ToString();
    }
    public class Cell {
        public string Value = "", Type = "", Style = ""; public bool Formula;
    }
    public class Sheet {
        public string Name, Member, Dimension; public bool Date1904;
        public int PhysicalRows, PhysicalCells, MaxRow, MaxColumn, FormulaNoCache;
        public List<string> Sheets = new List<string>();
        public Dictionary<int, Dictionary<string, Cell>> Rows = new Dictionary<int, Dictionary<string, Cell>>();
    }
    public static Sheet ReadSheet(string path, bool roleOnly) {
        Stopwatch timer = Stopwatch.StartNew(); Sheet result = new Sheet();
        using (Zip zip = new Zip(path)) {
            XmlDocument wb = Document(zip, "xl/workbook.xml");
            XmlNode props = wb.SelectSingleNode("//*[local-name()='workbookPr']");
            if (props != null) result.Date1904 = props.Attributes["date1904"] != null && (props.Attributes["date1904"].Value == "1" || props.Attributes["date1904"].Value == "true");
            XmlNodeList sheets = wb.SelectNodes("//*[local-name()='sheets']/*[local-name()='sheet']");
            if (sheets.Count == 0) throw new InvalidDataException("Workbook has no worksheet");
            foreach (XmlNode sheet in sheets) result.Sheets.Add(sheet.Attributes["name"].Value);
            XmlNode first = sheets[0]; result.Name = first.Attributes["name"].Value;
            string rid = ""; foreach (XmlAttribute a in first.Attributes) if (a.LocalName == "id") rid = a.Value;
            XmlDocument rels = Document(zip, "xl/_rels/workbook.xml.rels"); string member = null, stringsMember = null;
            foreach (XmlNode rel in rels.DocumentElement.ChildNodes) {
                if (rel.Attributes == null || rel.Attributes["Target"] == null) continue;
                string target = rel.Attributes["Target"].Value;
                string normalized = new Uri(new Uri("http://probe.invalid/xl/"), target).AbsolutePath.TrimStart('/');
                normalized = Uri.UnescapeDataString(normalized);
                if (rel.Attributes["Id"] != null && rel.Attributes["Id"].Value == rid) {
                    if (rel.Attributes["TargetMode"] != null && rel.Attributes["TargetMode"].Value == "External") throw new InvalidDataException("External worksheet target");
                    member = normalized;
                }
                if (rel.Attributes["Type"] != null && rel.Attributes["Type"].Value.EndsWith("/sharedStrings")) stringsMember = normalized;
            }
            if (member == null) throw new InvalidDataException("First-sheet relationship not found"); result.Member = member;
            Dictionary<int, List<Cell>> wanted = new Dictionary<int, List<Cell>>();
            using (XmlReader reader = Xml(zip.Open(member))) {
                while (reader.Read()) {
                    if (timer.Elapsed.TotalSeconds > 45) throw new TimeoutException("Workbook inspection exceeded 45 seconds");
                    if (reader.NodeType != XmlNodeType.Element) continue;
                    if (reader.LocalName == "dimension") result.Dimension = reader.GetAttribute("ref");
                    if (reader.LocalName == "row") result.PhysicalRows++;
                    if (reader.LocalName != "c") continue;
                    result.PhysicalCells++; string address = reader.GetAttribute("r") ?? ""; int pos = 0, colNum = 0;
                    while (pos < address.Length && address[pos] >= 'A' && address[pos] <= 'Z') { colNum = colNum * 26 + address[pos] - 'A' + 1; pos++; }
                    int row; if (!Int32.TryParse(address.Substring(pos), out row)) continue;
                    result.MaxRow = Math.Max(result.MaxRow, row); result.MaxColumn = Math.Max(result.MaxColumn, colNum);
                    string col = address.Substring(0, pos);
                    // Role workbooks: never decode C/password cells. FU: inspect A:F only.
                    if (colNum < 1 || colNum > (roleOnly ? 2 : 6)) continue;
                    Cell cell = new Cell(); cell.Type = reader.GetAttribute("t") ?? "n"; cell.Style = reader.GetAttribute("s") ?? "";
                    XmlDocument cellDoc = new XmlDocument(); cellDoc.XmlResolver = null;
                    using (XmlReader sub = reader.ReadSubtree()) cellDoc.Load(sub);
                    XmlNode v = cellDoc.SelectSingleNode("//*[local-name()='v']"); cell.Value = v == null ? "" : v.InnerText;
                    cell.Formula = cellDoc.SelectSingleNode("//*[local-name()='f']") != null;
                    if (cell.Formula && v == null) result.FormulaNoCache++;
                    if (cell.Type == "inlineStr") cell.Value = TextNodes(cellDoc);
                    if (cell.Type == "s") {
                        int si; if (!Int32.TryParse(cell.Value, out si)) throw new InvalidDataException("Invalid shared-string reference at " + address);
                        if (!wanted.ContainsKey(si)) wanted[si] = new List<Cell>(); wanted[si].Add(cell); cell.Value = "";
                    }
                    if (!result.Rows.ContainsKey(row)) result.Rows[row] = new Dictionary<string, Cell>(); result.Rows[row][col] = cell;
                    if (result.Rows.Count > 100000) throw new NotSupportedException("Probe row cap reached (100000 physical selected-column rows)");
                }
            }
            if (wanted.Count > 0) {
                if (stringsMember == null) stringsMember = "xl/sharedStrings.xml";
                int index = 0;
                using (XmlReader reader = Xml(zip.Open(stringsMember))) {
                    while (reader.Read()) {
                        if (timer.Elapsed.TotalSeconds > 45) throw new TimeoutException("Shared-string inspection exceeded 45 seconds");
                        if (reader.NodeType != XmlNodeType.Element || reader.LocalName != "si") continue;
                        List<Cell> refs;
                        if (wanted.TryGetValue(index, out refs)) {
                            XmlDocument d = new XmlDocument(); d.XmlResolver = null;
                            using (XmlReader sub = reader.ReadSubtree()) d.Load(sub);
                            string value = TextNodes(d); foreach (Cell c in refs) c.Value = value; wanted.Remove(index);
                        }
                        // Unreferenced shared strings, including passwords, are not materialized.
                        index++;
                    }
                }
                if (wanted.Count != 0) throw new InvalidDataException("Missing shared-string indexes");
            }
        }
        return result;
    }
    [DllImport("kernel32", CharSet=CharSet.Unicode, SetLastError=true)] static extern IntPtr LoadLibraryEx(string path, IntPtr file, uint flags);
    [DllImport("kernel32", CharSet=CharSet.Ansi)] static extern IntPtr GetProcAddress(IntPtr dll, string name);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] delegate int OpenDb(byte[] name, out IntPtr db, int flags, IntPtr vfs);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] delegate int CloseDb(IntPtr db);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] delegate int Prepare(IntPtr db, byte[] sql, int length, out IntPtr stmt, IntPtr tail);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] delegate int Step(IntPtr stmt);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] delegate int FinalizeStmt(IntPtr stmt);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] delegate int ColumnCount(IntPtr stmt);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] delegate IntPtr ColumnText(IntPtr stmt, int index);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] delegate IntPtr ErrorText(IntPtr db);
    static IntPtr library;
    static Delegate Function(string name, Type type) { IntPtr p = GetProcAddress(library, name); if (p == IntPtr.Zero) throw new InvalidOperationException(name + " unavailable"); return Marshal.GetDelegateForFunctionPointer(p, type); }
    static string Utf8(IntPtr p) { if (p == IntPtr.Zero) return ""; int n = 0; while (n < 65536 && Marshal.ReadByte(p, n) != 0) n++; byte[] b = new byte[n]; Marshal.Copy(p, b, 0, n); return Encoding.UTF8.GetString(b); }
    public static void LoadSqlite(string absolutePath) { library = LoadLibraryEx(absolutePath, IntPtr.Zero, 8); if (library == IntPtr.Zero) throw new System.ComponentModel.Win32Exception(Marshal.GetLastWin32Error()); }
    public static List<Dictionary<string,string>> Query(string privateCopy, string sql) {
        if (!(sql.StartsWith("SELECT ") || sql.StartsWith("PRAGMA table_info("))) throw new InvalidOperationException("Read-only query required");
        OpenDb open = (OpenDb)Function("sqlite3_open_v2", typeof(OpenDb)); CloseDb close = (CloseDb)Function("sqlite3_close", typeof(CloseDb));
        Prepare prepare = (Prepare)Function("sqlite3_prepare_v2", typeof(Prepare)); Step step = (Step)Function("sqlite3_step", typeof(Step));
        FinalizeStmt finish = (FinalizeStmt)Function("sqlite3_finalize", typeof(FinalizeStmt)); ColumnCount count = (ColumnCount)Function("sqlite3_column_count", typeof(ColumnCount));
        ColumnText name = (ColumnText)Function("sqlite3_column_name", typeof(ColumnText)); ColumnText text = (ColumnText)Function("sqlite3_column_text", typeof(ColumnText)); ErrorText error = (ErrorText)Function("sqlite3_errmsg", typeof(ErrorText));
        IntPtr db = IntPtr.Zero, stmt = IntPtr.Zero; List<Dictionary<string,string>> rows = new List<Dictionary<string,string>>();
        try {
            // SQLITE_OPEN_READONLY. Never open the real shared database with SQLite.
            if (open(Encoding.UTF8.GetBytes(privateCopy + "\0"), out db, 1, IntPtr.Zero) != 0) throw new InvalidOperationException(Utf8(error(db)));
            byte[] bytes = Encoding.UTF8.GetBytes(sql + "\0"); if (prepare(db, bytes, bytes.Length, out stmt, IntPtr.Zero) != 0) throw new InvalidOperationException(Utf8(error(db)));
            int rc; while ((rc = step(stmt)) == 100) {
                Dictionary<string,string> row = new Dictionary<string,string>(); for (int i = 0; i < count(stmt); i++) row[Utf8(name(stmt, i))] = Utf8(text(stmt, i)); rows.Add(row);
                if (rows.Count >= 1000) break;
            }
            if (rc != 101 && rc != 100) throw new InvalidOperationException(Utf8(error(db)));
            return rows;
        } finally { if (stmt != IntPtr.Zero) finish(stmt); if (db != IntPtr.Zero) close(db); }
    }
    public static void CopyReadOnly(string source, string destination) {
        using (FileStream input = new FileStream(source, FileMode.Open, FileAccess.Read, FileShare.ReadWrite))
        using (FileStream output = new FileStream(destination, FileMode.CreateNew, FileAccess.Write, FileShare.None)) {
            byte[] buffer = new byte[65536]; int n; while ((n = input.Read(buffer, 0, buffer.Length)) > 0) output.Write(buffer, 0, n);
        }
    }
}
'@

$report = @{
    probe_version = '1.0'; started = (Get-Date).ToString('o'); complete = $false
    safety = 'Read-only source inspection. No Excel/Registry/account writes. No Python/EXE execution. Raw Registry copies never included in report.'
    limitations = @('Not attached to the running Python/Tk interpreter. Cannot observe its in-memory DataFrame or recover previously swallowed exceptions.', 'Workbook counts below are structural, not a reimplementation of role/date/Registry business filtering.', 'An empty crash.log does NOT rule out a Tk callback or tab-preload exception in a windowed EXE.')
    errors = @(); warnings = @()
}
function Save-Report([string]$Phase) {
    $report['phase'] = $Phase
    if (Get-Command ConvertTo-Json -ErrorAction SilentlyContinue) { $json = ConvertTo-Json -InputObject $report -Depth 14 }
    else { $json = $script:serializer.Serialize($report) }
    [IO.File]::WriteAllText((Join-Path $ReportDir 'report.json'), $json, [Text.Encoding]::UTF8)
    [IO.File]::WriteAllText((Join-Path $ReportDir 'progress.txt'), $Phase, [Text.Encoding]::UTF8)
}
function Read-Json([string]$Path) {
    if (-not [IO.File]::Exists($Path)) { return @{} }
    try { return $script:serializer.DeserializeObject([IO.File]::ReadAllText($Path, [Text.Encoding]::UTF8)) }
    catch { $report.errors += ('JSON read failed: ' + $Path + ' : ' + $_.Exception.Message); return @{} }
}
function Select-Fields($Object, [string[]]$Names) {
    $selected = @{}; foreach ($key in $Names) { if ($Object -and $Object.ContainsKey($key)) { $selected[$key] = $Object[$key] } }; return $selected
}
function File-Info([string]$Path, [bool]$Hash = $false) {
    $timer = [Diagnostics.Stopwatch]::StartNew()
    $entry = @{ path = $Path; exists = [IO.File]::Exists($Path) }
    if ($entry.exists) {
        try {
            $fi = New-Object IO.FileInfo($Path); $entry.size = $fi.Length; $entry.modified_utc = $fi.LastWriteTimeUtc.ToString('o')
            if ($Hash -and $fi.Length -le 134217728) {
                $stream = [IO.File]::Open($Path, 'Open', 'Read', 'ReadWrite'); $sha = [Security.Cryptography.SHA256]::Create()
                try { $entry.sha256 = [BitConverter]::ToString($sha.ComputeHash($stream)).Replace('-', '').ToLowerInvariant() } finally { $sha.Dispose(); $stream.Close() }
            }
        } catch { $entry.error = $_.Exception.Message }
    }
    $entry.elapsed_ms = $timer.ElapsedMilliseconds; return $entry
}
function Cell-Text($Row, [string]$Column) {
    if ($Row.ContainsKey($Column)) { return $Row[$Column].Value.Trim() }; return ''
}

function Read-LogTail([string]$Path) {
    $stream = [IO.File]::Open($Path, 'Open', 'Read', 'ReadWrite'); $reader = $null
    try {
        $start = [Math]::Max(0, $stream.Length - 98304); $stream.Position = $start
        $reader = New-Object IO.StreamReader($stream, [Text.Encoding]::UTF8, $true)
        if ($start -gt 0) { [void]$reader.ReadLine() }
        return $reader.ReadToEnd()
    } finally { if ($reader) { $reader.Close() } else { $stream.Close() } }
}
function Inspect-Fu([string]$Path) {
    $summary = File-Info $Path $true; $timer = [Diagnostics.Stopwatch]::StartNew()
    try {
        if ([IO.Path]::GetExtension($Path).ToLowerInvariant() -eq '.xls') { throw 'Legacy XLS: not parsed by this OOXML-only probe; this is not an application error.' }
        $sheet = [FuProbe]::ReadSheet($Path, $false)
        $summary.sheet_names = @($sheet.Sheets); $summary.selected_sheet = $sheet.Name; $summary.xml_member = $sheet.Member
        $summary.declared_dimension = $sheet.Dimension; $summary.physical_rows = $sheet.PhysicalRows; $summary.physical_cells = $sheet.PhysicalCells
        $summary.max_physical_row = $sheet.MaxRow; $summary.max_physical_column = $sheet.MaxColumn; $summary.date1904 = $sheet.Date1904
        $summary.formula_without_cached_value = $sheet.FormulaNoCache
        $summary.headers = @{}; $summary.column_types = @{}; $summary.nonempty_by_column = @{}
        $summary.rows_with_plan_and_blank_actual = 0; $summary.rows_with_internal_code = 0; $summary.rows_missing_internal_code_with_plan = 0
        $summary.rows_owned_by_current_account = 0; $summary.non_bmp_cells = @(); $summary.excel_error_cells = @(); $summary.duplicate_code_groups = 0
        $codes = New-Object 'System.Collections.Generic.Dictionary[string,int]'; $bodyRows = 0
        foreach ($n in $sheet.Rows.Keys) {
            $row = $sheet.Rows[$n]
            if ($n -eq 1) {
                foreach ($c in $row.Keys) {
                    $text = $row[$c].Value
                    if ($text -match '^(文件编码|文件编号|内部编码|内部编号|中文标题|中文名称|实际FU日期|实际FU|FU计划|计划FU日期|责任人|设计人员|负责人|编制人)$') { $summary.headers[$c] = $text }
                    else { $summary.headers[$c] = '[unrecognized header; length=' + $text.Length + ']' }
                }
                continue
            }
            $bodyRows++; $code = Cell-Text $row 'B'; $plan = Cell-Text $row 'E'; $actual = Cell-Text $row 'D'
            if ($code) { $summary.rows_with_internal_code++; if (-not $codes.ContainsKey($code)) { $codes[$code] = 0 }; $codes[$code]++ }
            elseif ($plan) { $summary.rows_missing_internal_code_with_plan++ }
            if ($plan -and -not $actual) { $summary.rows_with_plan_and_blank_actual++ }
            $owner = Cell-Text $row 'F'
            if ($currentName -and $owner.Contains($currentName)) { $summary.rows_owned_by_current_account++ }
            foreach ($c in $row.Keys) {
                $cell = $row[$c]; $key = $c + ':' + $cell.Type
                if (-not $summary.column_types.ContainsKey($key)) { $summary.column_types[$key] = 0 }; $summary.column_types[$key]++
                if ($cell.Value) { if (-not $summary.nonempty_by_column.ContainsKey($c)) { $summary.nonempty_by_column[$c] = 0 }; $summary.nonempty_by_column[$c]++ }
                if ($cell.Type -eq 'e' -and $summary.excel_error_cells.Count -lt 20) { $summary.excel_error_cells += ($c + $n) }
                if ($cell.Value -match '[\uD800-\uDBFF][\uDC00-\uDFFF]' -and $summary.non_bmp_cells.Count -lt 20) { $summary.non_bmp_cells += ($c + $n) }
            }
        }
        $summary.selected_column_body_rows = $bodyRows
        $summary.duplicate_code_groups = @($codes.Values | Where-Object { $_ -gt 1 }).Count
        $after = File-Info $Path
        $summary.source_changed_during_read = ($after.size -ne $summary.size -or $after.modified_utc -ne $summary.modified_utc)
    } catch { $summary.error = $_.Exception.Message }
    $summary.inspection_ms = $timer.ElapsedMilliseconds; return $summary
}

try {
    Add-Type -AssemblyName System.Web.Extensions
    $script:serializer = New-Object Web.Script.Serialization.JavaScriptSerializer
    $script:serializer.MaxJsonLength = 16777216
    Save-Report '1/7 Environment and package'
    try { Add-Type -TypeDefinition $supportSource -Language CSharp -ReferencedAssemblies System.dll,System.Xml.dll -ErrorAction Stop -WarningAction SilentlyContinue }
    catch { $report.warnings += ('Native/XML helpers unavailable; environment/config/log collection will continue: ' + $_.Exception.Message) }
    $runtimeDir = Join-Path $ExeDir '_internal'
    if (-not [IO.Directory]::Exists($runtimeDir)) { $runtimeDir = $ExeDir }
    $report.environment = @{
        os = [Environment]::OSVersion.VersionString; powershell = $PSVersionTable.PSVersion.ToString(); clr = [Environment]::Version.ToString()
        process_bits = [IntPtr]::Size * 8; culture = [Globalization.CultureInfo]::CurrentCulture.Name
        ui_culture = [Globalization.CultureInfo]::CurrentUICulture.Name; utc_now = (Get-Date).ToUniversalTime().ToString('o')
        timezone = [TimeZoneInfo]::Local.Id; exe_dir = $ExeDir; runtime_dir = $runtimeDir; profile_dir = $ProfileDir
    }
    try { $os = Get-WmiObject Win32_OperatingSystem; $report.environment.windows_caption = $os.Caption; $report.environment.windows_version = $os.Version; $report.environment.windows_architecture = $os.OSArchitecture } catch { $report.environment.wmi_error = $_.Exception.Message }
    try { $report.environment.desktop_dpi = (Get-ItemProperty -LiteralPath 'HKCU:\Control Panel\Desktop' -Name LogPixels).LogPixels } catch {}
    $report.package = @()
    $exeFiles = @(Get-ChildItem -LiteralPath $ExeDir | Where-Object { -not $_.PSIsContainer -and $_.Extension -eq '.exe' })
    foreach ($exe in $exeFiles) { $entry = File-Info $exe.FullName $true; $entry.pe_machine = Get-PeMachine $exe.FullName; $report.package += $entry }
    foreach ($leaf in @('python38.dll', '_tkinter.pyd', 'tcl86t.dll', 'tk86t.dll', 'sqlite3.dll', '_sqlite3.pyd', 'base_library.zip', 'config.json', 'version.json', '_tcl_data\init.tcl', '_tk_data\tk.tcl')) { $report.package += File-Info (Join-Path $runtimeDir $leaf) ($leaf -ne 'config.json') }
    $report.versions = @{ beside_exe = Select-Fields (Read-Json (Join-Path $ExeDir 'version.json')) @('version'); bundled = Select-Fields (Read-Json (Join-Path $runtimeDir 'version.json')) @('version') }
    $report.running_applications = @()
    try {
        foreach ($p in @(Get-WmiObject Win32_Process -Filter "Name = '接口筛选.exe'")) {
            $report.running_applications += @{ pid = $p.ProcessId; executable_path = $p.ExecutablePath; session_id = $p.SessionId; created = $p.CreationDate }
        }
    } catch { $report.errors += ('Process inspection: ' + $_.Exception.Message) }
    Save-Report '2/7 Relevant configuration and current role'
    $bundled = Read-Json (Join-Path $runtimeDir 'config.json'); $beside = Read-Json (Join-Path $ExeDir 'config.json'); $user = Read-Json (Join-Path $ProfileDir 'config.json')
    $keys = @('user_name', 'folder_path', 'department_profile', 'folder_path_lock_enabled', 'auto_hide_overdue_enabled', 'auto_hide_overdue_days', 'hide_previous_months', 'role_export_days', 'registry_enabled', 'registry_db_path', 'registry_wal', 'registry_force_network_mode', 'registry_local_cache_enabled', 'registry_local_cache_sync_interval', 'registry_query_cache_enabled', 'registry_query_cache_ttl')
    $report.config = @{ bundled = Select-Fields $bundled $keys; beside_exe = Select-Fields $beside $keys; user = Select-Fields $user $keys }
    $profileName = '建筑结构所'; if ($bundled.ContainsKey('department_profile')) { $profileName = $bundled['department_profile'] }
    $profile = @{}; if ($bundled.ContainsKey('department_profiles') -and $bundled['department_profiles'].ContainsKey($profileName)) { $profile = $bundled['department_profiles'][$profileName] }
    $report.config.selected_profile = Select-Fields $profile @('organization_filter', 'department_codes', 'department_code_mapping', 'director_role_mapping', 'role_export_days', 'projects', 'role_table_file', 'default_folder_path')
    $currentName = ''; if ($user.ContainsKey('user_name')) { $currentName = [string]$user['user_name'] } elseif ($bundled.ContainsKey('user_name')) { $currentName = [string]$bundled['user_name'] }
    $roleRelative = 'excel_bin/姓名角色表.xlsx'; if ($profile.ContainsKey('role_table_file')) { $roleRelative = $profile['role_table_file'] }
    $rolePath = Join-Path $runtimeDir $roleRelative
    $report.role = @{ path = $rolePath; current_account = $currentName; account_matches = 0; current_roles = @(); password_column = 'NOT DECODED / NOT EXPORTED' }
    try {
        $roleSheet = [FuProbe]::ReadSheet($rolePath, $true)
        foreach ($n in $roleSheet.Rows.Keys) {
            $row = $roleSheet.Rows[$n]
            if ($currentName -and [string]::Equals((Cell-Text $row 'A'), $currentName, [StringComparison]::Ordinal)) { $report.role.account_matches++; $report.role.current_roles += (Cell-Text $row 'B') }
        }
    } catch { $report.role.error = $_.Exception.Message }
    if (-not $DataFolder) {
        $DataFolder = [string]$user['folder_path']
        $locked = $true; if ($bundled.ContainsKey('folder_path_lock_enabled')) { $locked = [bool]$bundled['folder_path_lock_enabled'] }
        $defaultFolder = [string]$profile['default_folder_path']
        if (-not $defaultFolder -and $bundled.ContainsKey('defaults')) { $defaultFolder = [string]$bundled['defaults']['folder_path'] }
        if (($locked -or -not $DataFolder) -and $defaultFolder) { $DataFolder = $defaultFolder }
        $report.config.path_resolution = 'Inferred from packaged lock/profile and user config; compare to the visible GUI path. Override with -DataFolder if different.'
    } else { $report.config.path_resolution = 'Explicit -DataFolder argument' }
    $report.data_folder = $DataFolder
    Save-Report '3/7 Existing error logs (bounded and redacted)'
    $report.logs = @()
    foreach ($leaf in @('crash.log', 'exit_reason.log', 'registry_diag.log')) {
        $path = Join-Path $ProfileDir $leaf; $entry = File-Info $path
        if ($entry.exists) {
            try {
                $lines = (Read-LogTail $path) -split "`r?`n"
                $entry.tail = @($lines | ForEach-Object { if ($_ -match '(?i)password|passwd|\bpwd\b|secret|token|credential|密码|口令') { '[sensitive line omitted]' } else { $_ } })
            } catch { $entry.error = $_.Exception.Message }
        }
        $report.logs += $entry
    }
    Save-Report '4/7 FU file discovery and physical worksheet inspection'
    $report.fu_files = @(); $report.fu_near_matches = @(); $report.excel_file_count = 0
    if ($DataFolder) {
        try {
            $timer = [Diagnostics.Stopwatch]::StartNew()
            $files = @(Get-ChildItem -LiteralPath $DataFolder | Where-Object { -not $_.PSIsContainer -and $_.Extension -match '^\.(xlsx|xlsm|xls)$' -and -not $_.Name.StartsWith('~$') })
            $report.excel_file_count = $files.Count; $report.folder_listing_ms = $timer.ElapsedMilliseconds
            $fu = @($files | Where-Object { $_.Name -match '^\d{4}项目标准表格\.(xlsx|xlsm|xls)$' } | Sort-Object Name)
            $report.fu_matched_count = $fu.Count
            $report.fu_near_matches = @($files | Where-Object { $_.Name -match '标准表格|FU' -and $_.Name -notmatch '^\d{4}项目标准表格\.(xlsx|xlsm|xls)$' } | ForEach-Object { $_.Name })
            foreach ($file in @($fu | Select-Object -First $MaxFuFiles)) {
                Save-Report ('4/7 Inspecting ' + $file.Name)
                $report.fu_files += Inspect-Fu $file.FullName
            }
            if ($fu.Count -gt $MaxFuFiles) { $report.warnings += 'FU inspection capped by -MaxFuFiles.' }
        } catch { $report.errors += ('FU discovery: ' + $_.Exception.Message) }
    } else { $report.warnings += 'No data folder could be inferred. Rerun with -DataFolder matching the GUI.' }
    Save-Report '5/7 Registry metadata and private-copy aggregate queries'
    $report.registry = @{}
    if ($DataFolder) {
        $registryPath = Join-Path $DataFolder '.registry\registry.db'
        # hooks._cfg uses exe-level config.json, not the profile's user config.
        if ($beside.ContainsKey('registry_db_path') -and $beside['registry_db_path']) { $registryPath = [string]$beside['registry_db_path'] }
        if (-not [IO.Path]::IsPathRooted($registryPath)) { $registryPath = Join-Path $ExeDir $registryPath }
        $report.registry.source = File-Info $registryPath
        $report.registry.sidecars = @(); foreach ($suffix in @('-wal', '-shm', '-journal')) { $report.registry.sidecars += File-Info ($registryPath + $suffix) }
        $report.registry.local_cache = File-Info (Join-Path $env:LOCALAPPDATA 'InterfaceFilter\cache\registry_local.db')
        $report.registry.consistency_note = 'Best-effort file copy, NOT a transactional backup. Source size/mtime checked before and after; journal/WAL activity can make a snapshot inconclusive. No source SQLite connection or business write.'
        if (-not $SkipRegistry -and $report.registry.source.exists) {
            try {
                if ($report.registry.source.size -gt 134217728) { throw 'Registry exceeds the 128 MiB probe limit; metadata only.' }
                $copy = Join-Path $PrivateDir 'registry.db'; $before = @(); $after = @()
                foreach ($suffix in @('', '-wal', '-journal')) {
                    $meta = File-Info ($registryPath + $suffix); $before += $meta
                    if ($meta.exists) {
                        if ($meta.size -gt 134217728) { throw 'Registry sidecar exceeds probe limit.' }
                        [FuProbe]::CopyReadOnly(($registryPath + $suffix), ($copy + $suffix))
                    }
                }
                foreach ($suffix in @('', '-wal', '-journal')) { $after += File-Info ($registryPath + $suffix) }
                $stable = $true
                for ($i = 0; $i -lt $before.Count; $i++) { if ($before[$i].exists -ne $after[$i].exists -or $before[$i].size -ne $after[$i].size -or $before[$i].modified_utc -ne $after[$i].modified_utc) { $stable = $false } }
                $report.registry.source_stable_during_copy = $stable
                if (-not $stable) { throw 'Registry changed during copying. Counts withheld; rerun when writes are idle.' }
                if ($before[2].exists -and $before[2].size -gt 0) { throw 'Rollback journal is present. Counts withheld; rerun after the active transaction finishes.' }
                [FuProbe]::LoadSqlite((Join-Path $runtimeDir 'sqlite3.dll'))
                $report.registry.sqlite_version = @([FuProbe]::Query($copy, 'SELECT sqlite_version() AS version'))
                $report.registry.tables = @([FuProbe]::Query($copy, "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"))
                $schema = @([FuProbe]::Query($copy, 'PRAGMA table_info(tasks)')); $report.registry.task_columns = @($schema | ForEach-Object { $_['name'] })
                $cols = $report.registry.task_columns
                if ($cols -contains 'file_type') {
                    $report.registry.counts_by_file_type = @([FuProbe]::Query($copy, 'SELECT file_type, count(*) AS count FROM tasks GROUP BY file_type'))
                    $groupCols = @('project_id', 'status', 'display_status', 'ignored') | Where-Object { $cols -contains $_ }
                    if ($groupCols) {
                        $group = $groupCols -join ', '
                        $report.registry.fu_status_counts = @([FuProbe]::Query($copy, ('SELECT ' + $group + ', count(*) AS count FROM tasks WHERE file_type=7 GROUP BY ' + $group)))
                    }
                    if ($cols -contains 'confirmed_at') { $report.registry.fu_confirmation_counts = @([FuProbe]::Query($copy, "SELECT CASE WHEN coalesce(confirmed_at,'')='' THEN 'not_confirmed' ELSE 'confirmed' END AS confirmation, count(*) AS count FROM tasks WHERE file_type=7 GROUP BY confirmation")) }
                    if ($currentName -and $cols -contains 'responsible_person' -and $cols -contains 'status') {
                        $safeName = $currentName.Replace("'", "''")
                        $report.registry.fu_current_account_exact_owner = @([FuProbe]::Query($copy, ("SELECT status, count(*) AS count FROM tasks WHERE file_type=7 AND responsible_person='" + $safeName + "' GROUP BY status")))
                    }
                }
            } catch { $report.registry.query_error = $_.Exception.Message }
        } else { $report.registry.query_skipped = $true }
    }
    Save-Report '6/7 Cache metadata (no pickle deserialization)'
    $report.cache = @()
    $cacheDir = Join-Path $ExeDir 'result_cache'
    if ([IO.Directory]::Exists($cacheDir)) {
        foreach ($file in @(Get-ChildItem -LiteralPath $cacheDir | Where-Object { -not $_.PSIsContainer } | Select-Object -First 150)) { $report.cache += File-Info $file.FullName }
    }
    $report.cache_note = 'Only names, sizes and timestamps collected. Pickle and queued task payloads are never executed or exported.'
    $report.finished = (Get-Date).ToString('o'); $report.complete = $true
    Save-Report '7/7 Complete'
    $readme = @'
FU diagnostic results

Send report.json (and TIMEOUT.txt / fatal.txt if present). No raw Excel or Registry database is included.
The report contains internal paths, the current account name/role, selected configuration, file hashes and redacted log excerpts. Review before sharing externally.

This probe does not repair or change anything. It cannot see a running EXE's Python objects or recover swallowed Tk exceptions.
rows_with_plan_and_blank_actual is a worksheet structure count, NOT the final GUI count (date windows, roles, archives and pending review still matter).
A query_error or unsupported XLS/ZIP format may be a probe limitation; it is not by itself proof of application failure.

For the strongest comparison, reproduce the blank FU tab first and leave the app open. Run the same probe beside the working local EXE and the failing deployed EXE, on the same account and source files if possible.
If logs are empty, use the app's Open Monitor / Save Log feature after reproducing, and send that saved log plus a screenshot separately. This probe does not operate GUI windows.
'@
    [IO.File]::WriteAllText((Join-Path $ReportDir 'README.txt'), $readme, [Text.Encoding]::UTF8)
} catch {
    $report.errors += $_.Exception.ToString()
    try { Save-Report 'Probe error (partial results retained)' } catch {}
    [IO.File]::WriteAllText((Join-Path $ReportDir 'fatal.txt'), $_.Exception.ToString(), [Text.Encoding]::UTF8)
}
