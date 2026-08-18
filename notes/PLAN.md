# План ребёнка

Обновлён 2026-08-18 10:32 UTC.

## Задание

как устроен TLS

## Что сделал сам

- прочитал «Transport Layer Security»
- сам пошёл: handshaking procedure
- прочитал «Handshake (computing)»
- прочитал «Transport Layer Security»
- сам пошёл: асимметричное шифрование, public key infrastructure

## Понял

- Transport Layer Security (TLS) is a cryptographic protocol designed to provide communications security over a computer network, such as the Internet.
- It runs in the presentation layer and is itself composed of two layers: the TLS record and the TLS handshake protocols.
- During this handshake, the client and server agree on various parameters used to establish the connection's security: The handshake begins when a client connects to a TLS-enabled server requesting a secure connection…
- To generate the session keys used for the secure connection, the client either: encrypts a random number (PreMasterSecret) with the server's public key and sends the result to the server (which only the server should…
- If any one of the above steps fails, then the TLS handshake fails and the connection is not created.
- TLS и SSL используют асимметричное шифрование для аутентификации, симметричное шифрование для конфиденциальности и коды аутентичности сообщений для сохранения целостности сообщений.
- In computing, a handshake is a process in which two devices establish a communication link by authenticating and validating each other's signals.
- Фаза переговоров: Клиент посылает сообщение ClientHello, указывая последнюю версию поддерживаемого TLS-протокола, случайное число и список поддерживаемых шифронаборов.

## Сам решил учить дальше

- public key infrastructure: В устройстве «TLS» это связано так: Mutual authentication requires public key infrastructure (PKI) deployment to clients.
- асимметричное шифрование: В устройстве «TLS» это связано так: TLS и SSL используют асимметричное шифрование для аутентификации, симметричное шифрование для конфиденциальности.
