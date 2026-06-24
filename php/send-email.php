<?php
/**
 * Обработчик email-уведомлений для Django-проекта инструктора по вождению.
 * Поддерживает действия: created, rescheduled, cancelled.
 * Вызывается из Django через HTTP POST.
 */

header('Content-Type: application/json; charset=utf-8');
header('Access-Control-Allow-Origin: https://ivan-gunichev.ru');
header('Access-Control-Allow-Methods: POST');
header('Access-Control-Allow-Headers: Content-Type');

// ── Защита токеном ────────────────────────────────────────────────────────────
$SECRET_TOKEN = 'GunichevMail2026xK9p';

$incoming_token = $_POST['token'] ?? '';
if ($incoming_token !== $SECRET_TOKEN) {
    http_response_code(403);
    echo json_encode(['success' => false, 'message' => 'Forbidden']);
    exit;
}

// ── Получаем поля ─────────────────────────────────────────────────────────────
$name    = htmlspecialchars($_POST['name']    ?? '', ENT_QUOTES, 'UTF-8');
$phone   = htmlspecialchars($_POST['phone']   ?? '', ENT_QUOTES, 'UTF-8');
$date    = htmlspecialchars($_POST['date']    ?? '', ENT_QUOTES, 'UTF-8');
$time    = htmlspecialchars($_POST['time']    ?? '', ENT_QUOTES, 'UTF-8');
$comment = htmlspecialchars($_POST['comment'] ?? '', ENT_QUOTES, 'UTF-8');
$action  = $_POST['action'] ?? 'created';

// ── Параметры по действию ─────────────────────────────────────────────────────
$actions = [
    'created'     => [
        'subject' => "📅 Клиент записался: {$name}",
        'heading' => 'Клиент записался',
        'color'   => '#4ECDC4',
        'icon'    => '📅',
    ],
    'rescheduled' => [
        'subject' => "🔄 Клиент перенёс запись: {$name}",
        'heading' => 'Клиент перенёс запись',
        'color'   => '#F7B731',
        'icon'    => '🔄',
    ],
    'cancelled'   => [
        'subject' => "❌ Клиент отменил запись: {$name}",
        'heading' => 'Клиент отменил запись',
        'color'   => '#FF6B6B',
        'icon'    => '❌',
    ],
];

$cfg     = $actions[$action] ?? [
    'subject' => "📬 Запись ({$action}): {$name}",
    'heading' => 'Уведомление о записи',
    'color'   => '#4ECDC4',
    'icon'    => '📬',
];

$subject = $cfg['subject'];
$heading = $cfg['heading'];
$color   = $cfg['color'];
$icon    = $cfg['icon'];

$name_val    = $name    ?: '<span style="color:#aaa;">не указано</span>';
$phone_val   = $phone   ?: '<span style="color:#aaa;">не указан</span>';
$date_val    = $date    ?: '<span style="color:#aaa;">не указана</span>';
$time_val    = $time    ?: '<span style="color:#aaa;">не указано</span>';

$comment_block = '';
if ($comment) {
    $comment_block = "
      <tr>
        <td style=\"padding: 0 32px 24px;\">
          <div style=\"background:#f5f5f5; border-left: 3px solid {$color}; border-radius: 4px; padding: 12px 16px;\">
            <p style=\"margin:0 0 4px; font-size:12px; color:#888; text-transform:uppercase; letter-spacing:.05em;\">Комментарий</p>
            <p style=\"margin:0; font-size:15px; color:#333; line-height:1.6;\">{$comment}</p>
          </div>
        </td>
      </tr>";
}

$sent_at = date('d.m.Y H:i');

// ── HTML-письмо ───────────────────────────────────────────────────────────────
$html = <<<HTML
<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{$subject}</title>
</head>
<body style="margin:0; padding:0; background:#f0f2f5; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;">

  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f0f2f5; padding: 32px 16px;">
    <tr>
      <td align="center">
        <table width="100%" cellpadding="0" cellspacing="0" style="max-width:520px; background:#ffffff; border-radius:12px; overflow:hidden; box-shadow: 0 2px 12px rgba(0,0,0,0.08);">

          <!-- Цветная шапка -->
          <tr>
            <td style="background:{$color}; padding: 28px 32px; text-align:center;">
              <p style="margin:0 0 6px; font-size:36px; line-height:1;">{$icon}</p>
              <h1 style="margin:0; font-size:22px; font-weight:700; color:#ffffff; letter-spacing:-0.02em;">{$heading}</h1>
            </td>
          </tr>

          <!-- Данные клиента -->
          <tr>
            <td style="padding: 28px 32px 8px;">
              <table width="100%" cellpadding="0" cellspacing="0">

                <tr>
                  <td style="padding: 10px 0; border-bottom: 1px solid #eeeeee;">
                    <span style="font-size:13px; color:#888; display:block; margin-bottom:2px;">Имя</span>
                    <span style="font-size:16px; font-weight:600; color:#1a1a1a;">{$name_val}</span>
                  </td>
                </tr>

                <tr>
                  <td style="padding: 10px 0; border-bottom: 1px solid #eeeeee;">
                    <span style="font-size:13px; color:#888; display:block; margin-bottom:2px;">Телефон</span>
                    <span style="font-size:16px; font-weight:600; color:#1a1a1a;">{$phone_val}</span>
                  </td>
                </tr>

                <tr>
                  <td style="padding: 10px 0; border-bottom: 1px solid #eeeeee;">
                    <span style="font-size:13px; color:#888; display:block; margin-bottom:2px;">Дата</span>
                    <span style="font-size:16px; font-weight:600; color:#1a1a1a;">{$date_val}</span>
                  </td>
                </tr>

                <tr>
                  <td style="padding: 10px 0; border-bottom: 1px solid #eeeeee;">
                    <span style="font-size:13px; color:#888; display:block; margin-bottom:2px;">Время</span>
                    <span style="font-size:16px; font-weight:600; color:#1a1a1a;">{$time_val}</span>
                  </td>
                </tr>

              </table>
            </td>
          </tr>

          <!-- Комментарий (если есть) -->
          {$comment_block}

          <!-- Кнопка и подвал -->
          <tr>
            <td style="padding: 20px 32px 32px; text-align:center;">
              <a href="https://ivan-gunichev.ru/dashboard/"
                 style="display:inline-block; padding: 12px 28px; background:{$color}; color:#ffffff; text-decoration:none; border-radius:8px; font-size:15px; font-weight:600; letter-spacing:0.01em;">
                Открыть личный кабинет
              </a>
              <p style="margin: 20px 0 0; font-size:12px; color:#aaa;">Отправлено {$sent_at} · ivan-gunichev.ru</p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>

</body>
</html>
HTML;

// Текстовая версия (fallback)
$text  = strtoupper($heading) . "\n";
$text .= str_repeat("─", 36) . "\n\n";
$text .= "Имя:      " . ($name    ?: 'не указано') . "\n";
$text .= "Телефон:  " . ($phone   ?: 'не указан')  . "\n";
$text .= "Дата:     " . ($date    ?: 'не указана') . "\n";
$text .= "Время:    " . ($time    ?: 'не указано') . "\n";
if ($_POST['comment'] ?? '') {
    $text .= "\nКомментарий:\n   " . ($_POST['comment']) . "\n";
}
$text .= "\n" . str_repeat("─", 36) . "\n";
$text .= "Кабинет: https://ivan-gunichev.ru/dashboard/\n";
$text .= "Отправлено: {$sent_at}\n";

// ── Multipart письмо (text + html) ───────────────────────────────────────────
$to       = "gialekseevich@yandex.ru";
$boundary = md5(uniqid('', true));

$headers  = "From: noreply@ivan-gunichev.ru\r\n";
$headers .= "Reply-To: noreply@ivan-gunichev.ru\r\n";
$headers .= "MIME-Version: 1.0\r\n";
$headers .= "Content-Type: multipart/alternative; boundary=\"{$boundary}\"\r\n";
$headers .= "X-Mailer: PHP/" . phpversion() . "\r\n";

$body  = "--{$boundary}\r\n";
$body .= "Content-Type: text/plain; charset=UTF-8\r\n";
$body .= "Content-Transfer-Encoding: base64\r\n\r\n";
$body .= chunk_split(base64_encode($text)) . "\r\n";

$body .= "--{$boundary}\r\n";
$body .= "Content-Type: text/html; charset=UTF-8\r\n";
$body .= "Content-Transfer-Encoding: base64\r\n\r\n";
$body .= chunk_split(base64_encode($html)) . "\r\n";

$body .= "--{$boundary}--";

$success = mail($to, '=?UTF-8?B?' . base64_encode($subject) . '?=', $body, $headers);

if ($success) {
    echo json_encode(['success' => true,  'message' => 'Письмо отправлено']);
} else {
    echo json_encode(['success' => false, 'message' => 'Ошибка mail()']);
}
?>
