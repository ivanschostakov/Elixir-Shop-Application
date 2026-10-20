<?php

if ($argc !== 3) { exit(2); }
umask(0077);
$root = rtrim($argv[1], '/');
$backup = rtrim($argv[2], '/');
if (str_starts_with($backup . '/', $root . '/')) { exit(2); }
if (!is_dir($backup)) { mkdir($backup, 0700, true); }
$settings = require $root . '/bitrix/.settings.php';
$c = $settings['connections']['value']['default'];
$db = new mysqli($c['host'], $c['login'], $c['password'], $c['database']);
$all = $db->query('SHOW TABLES');
$tables = [];
$exact = ['b_user', 'b_user_group', 'b_uts_user', 'b_utm_user', 'b_sale_discount_coupon', 'b_sale_discount_coupon_counter'];
while ($row = $all->fetch_row()) {
    if (in_array($row[0], $exact, true) || str_starts_with($row[0], 'b_elixir_referral_')) {
        $tables[] = $row[0];
    }
}
foreach (['b_user', 'b_user_group', 'b_elixir_referral_app_purchase', 'b_elixir_referral_partner_accrual'] as $required) {
    if (!in_array($required, $tables, true)) { throw new RuntimeException('Required backup table missing'); }
}
$file = $backup . '/bonus-tables.sql.gz';
$args = array_merge(['mysqldump', '--host=' . $c['host'], '--user=' . $c['login'],
    '--single-transaction', '--quick', '--hex-blob', '--triggers', '--default-character-set=utf8mb4', $c['database']], $tables);
$env = array_merge($_ENV, ['MYSQL_PWD' => $c['password']]);
$process = proc_open($args, [0 => ['file', '/dev/null', 'r'], 1 => ['pipe', 'w'],
    2 => ['file', $backup . '/bonus-dump.stderr.log', 'w']], $pipes, null, $env);
if (!is_resource($process)) { throw new RuntimeException('Could not start bonus backup'); }
$zip = gzopen($file . '.partial', 'wb6');
while (!feof($pipes[1])) {
    $chunk = fread($pipes[1], 1024 * 1024);
    if ($chunk === false) { throw new RuntimeException('Backup stream failed'); }
    if ($chunk !== '') { gzwrite($zip, $chunk); }
}
fclose($pipes[1]);
gzclose($zip);
if (proc_close($process) !== 0) { throw new RuntimeException('Bonus database backup failed'); }
rename($file . '.partial', $file);
$tar = proc_open(['tar', '-czf', $backup . '/bonus-files.tar.gz', '-C', $root,
    'local/modules/elixir.promo', 'bitrix/tools/elixir.promo'],
    [0 => ['file', '/dev/null', 'r'], 1 => ['file', '/dev/null', 'w'],
    2 => ['file', $backup . '/bonus-tar.stderr.log', 'w']], $unused);
if (!is_resource($tar) || proc_close($tar) !== 0) { throw new RuntimeException('Bonus file backup failed'); }
$manifest = ['created_at' => date(DATE_ATOM), 'tables' => $tables,
    'database_bytes' => filesize($file), 'database_sha256' => hash_file('sha256', $file)];
file_put_contents($backup . '/bonus-manifest.json', json_encode($manifest, JSON_PRETTY_PRINT));
echo json_encode(['backup' => $backup, 'table_count' => count($tables), 'database_bytes' => filesize($file)]), PHP_EOL;
