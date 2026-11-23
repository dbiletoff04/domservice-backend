-- Начальное заполнение справочников (правило 9 целостности данных Р1)

INSERT INTO user_role (role_code, name, description) VALUES
    ('resident',   'Житель',          'Подаёт заявки, смотрит статусы, получает уведомления, подтверждает или возвращает работу'),
    ('dispatcher', 'Диспетчер',       'Регистрирует заявки по звонку, назначает мастера и срок, обрабатывает возвраты'),
    ('master',     'Мастер',          'Видит назначенные заявки, отмечает выполнение'),
    ('manager',    'Руководитель УК', 'Формирует отчёт для ГИС ЖКХ')
ON CONFLICT (role_code) DO NOTHING;

INSERT INTO request_status (status_code, name, description) VALUES
    ('accepted',             'Принята',               'Заявка создана жителем или диспетчером'),
    ('master_assigned',      'Мастер назначен',       'Назначены мастер и ориентировочный срок; после возврата выполняется заново'),
    ('pending_confirmation', 'Ожидает подтверждения', 'Мастер отметил работу выполненной, ожидается ответ жителя'),
    ('closed',               'Закрыта',               'Житель подтвердил выполнение работ'),
    ('returned',             'Возвращена',            'Житель сообщил, что проблема не решена; комментарий сохранён в истории')
ON CONFLICT (status_code) DO NOTHING;

INSERT INTO management_company (name, contact_phone) VALUES
    ('УК «Домсервис» (пилот)', '+78443000000')
ON CONFLICT (name) DO NOTHING;

INSERT INTO problem_category (name, is_active) VALUES
    ('Сантехника',   TRUE),
    ('Электрика',    TRUE),
    ('Отопление',    TRUE),
    ('Водоснабжение',TRUE),
    ('Лифт',         TRUE),
    ('Другое',       TRUE)
ON CONFLICT (name) DO NOTHING;