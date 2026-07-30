<?php

declare(strict_types=1);

set_time_limit(0);

if ($argc !== 3) {
    fwrite(STDERR, "Usage: php backup_bitrix.php <document-root> <backup-directory>\n");
    exit(2);
}

$documentRoot = rtrim((string)$argv[1], '/');
$backupDirectory = rtrim((string)$argv[2], '/');
$settingsPath = $documentRoot . '/bitrix/.settings.php';
if (
    $documentRoot === ''
    || $backupDirectory === ''
    || str_starts_with($backupDirectory . '/', $documentRoot . '/')
    || !is_file($settingsPath)
) {
    fwrite(STDERR, "Invalid backup paths\n");
    exit(2);
}
if (!is_dir($backupDirectory) && !mkdir($backupDirectory, 0700, true) && !is_dir($backupDirectory)) {
    fwrite(STDERR, "Could not create backup directory\n");
    exit(2);
}
chmod($backupDirectory, 0700);

$settings = require $settingsPath;
$connection = $settings['connections']['value']['default'] ?? null;
if (!is_array($connection)) {
    fwrite(STDERR, "Bitrix database settings were not found\n");
    exit(2);
}
foreach (['host', 'database', 'login', 'password'] as $requiredKey) {
    if (!isset($connection[$requiredKey]) || trim((string)$connection[$requiredKey]) === '') {
        fwrite(STDERR, "Bitrix database settings are incomplete\n");
        exit(2);
    }
}

$filesArchive = $backupDirectory . '/affected-files.tar.gz';
$candidatePaths = [
    'local/modules/elixir.promo',
    'local/modules/elixir.reviewsync',
    'local/modules/elixir.delivery',
    'local/modules/elixir.catalogsync',
    'local/api/app_integration.php',
    'bitrix/tools/elixir.promo/api.php',
    'bitrix/tools/elixir.reviewsync',
    'bitrix/tools/elixir.delivery',
    'bitrix/tools/elixir.catalogsync',
];
$relativePaths = array_values(array_filter(
    $candidatePaths,
    static fn(string $path): bool => file_exists($documentRoot . '/' . $path)
));
if ($relativePaths === []) {
    fwrite(STDERR, "No affected files were found for backup\n");
    exit(2);
}
$tarCommand = array_merge(
    ['tar', '-czf', $filesArchive, '-C', $documentRoot],
    $relativePaths
);
$tarProcess = proc_open(
    $tarCommand,
    [
        0 => ['file', '/dev/null', 'r'],
        1 => ['file', $backupDirectory . '/tar.stdout.log', 'a'],
        2 => ['file', $backupDirectory . '/tar.stderr.log', 'a'],
    ],
    $tarPipes
);
if (!is_resource($tarProcess) || proc_close($tarProcess) !== 0 || !is_file($filesArchive)) {
    fwrite(STDERR, "Affected-file backup failed\n");
    exit(1);
}

$databaseArchive = $backupDirectory . '/bitrix-database.sql.gz';
$databasePartial = $databaseArchive . '.partial';
$dumpCommand = [
    'mysqldump',
    '--host=' . (string)$connection['host'],
    '--port=' . (string)($connection['port'] ?? '3306'),
    '--user=' . (string)$connection['login'],
    '--single-transaction',
    '--quick',
    '--routines',
    '--triggers',
    '--events',
    '--hex-blob',
    '--default-character-set=utf8mb4',
    (string)$connection['database'],
];
$environment = $_ENV;
$environment['MYSQL_PWD'] = (string)$connection['password'];
$dumpProcess = proc_open(
    $dumpCommand,
    [
        0 => ['file', '/dev/null', 'r'],
        1 => ['pipe', 'w'],
        2 => ['file', $backupDirectory . '/mysqldump.stderr.log', 'a'],
    ],
    $dumpPipes,
    null,
    $environment
);
if (!is_resource($dumpProcess)) {
    fwrite(STDERR, "Could not start mysqldump\n");
    exit(1);
}

$gzip = gzopen($databasePartial, 'wb6');
if ($gzip === false) {
    proc_terminate($dumpProcess);
    proc_close($dumpProcess);
    fwrite(STDERR, "Could not create compressed database archive\n");
    exit(1);
}
while (!feof($dumpPipes[1])) {
    $chunk = fread($dumpPipes[1], 1024 * 1024);
    if ($chunk === false) {
        gzclose($gzip);
        proc_terminate($dumpProcess);
        proc_close($dumpProcess);
        fwrite(STDERR, "Could not read mysqldump output\n");
        exit(1);
    }
    if ($chunk !== '') {
        gzwrite($gzip, $chunk);
    }
}
fclose($dumpPipes[1]);
gzclose($gzip);
$dumpExitCode = proc_close($dumpProcess);
if ($dumpExitCode !== 0) {
    fwrite(STDERR, "mysqldump failed with exit code " . $dumpExitCode . "\n");
    exit(1);
}
if (!rename($databasePartial, $databaseArchive)) {
    fwrite(STDERR, "Could not finalize database archive\n");
    exit(1);
}
chmod($databaseArchive, 0600);
chmod($filesArchive, 0600);

$manifest = [
    'created_at' => date(DATE_ATOM),
    'document_root' => $documentRoot,
    'database' => (string)$connection['database'],
    'database_archive' => basename($databaseArchive),
    'database_bytes' => filesize($databaseArchive),
    'database_sha256' => hash_file('sha256', $databaseArchive),
    'files_archive' => basename($filesArchive),
    'files_bytes' => filesize($filesArchive),
    'files_sha256' => hash_file('sha256', $filesArchive),
    'affected_paths' => $relativePaths,
];
file_put_contents(
    $backupDirectory . '/manifest.json',
    json_encode($manifest, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES) . PHP_EOL,
    LOCK_EX
);
chmod($backupDirectory . '/manifest.json', 0600);

echo json_encode([
    'ok' => true,
    'backup_directory' => $backupDirectory,
    'database_bytes' => $manifest['database_bytes'],
    'files_bytes' => $manifest['files_bytes'],
], JSON_UNESCAPED_SLASHES) . PHP_EOL;
