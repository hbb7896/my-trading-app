import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import 'api.dart';

class AuthGate extends StatefulWidget {
  final Widget Function(TradingApi? api) child;
  const AuthGate({super.key, required this.child});
  @override
  State<AuthGate> createState() => _AuthGateState();
}

class _AuthGateState extends State<AuthGate> {
  final server = TextEditingController(),
      email = TextEditingController(),
      password = TextEditingController();
  bool loading = true, busy = false, local = false, allowed = false;
  String? error;
  SupabaseClient? client;
  StreamSubscription<AuthState>? subscription;
  int sequence = 0;
  @override
  void initState() {
    super.initState();
    load();
  }

  @override
  void dispose() {
    subscription?.cancel();
    server.dispose();
    email.dispose();
    password.dispose();
    super.dispose();
  }

  Future<void> load() async {
    setState(() {
      loading = true;
      error = null;
    });
    try {
      final prefs = await SharedPreferences.getInstance();
      if (server.text.isEmpty) {
        server.text =
            prefs.getString('api_url') ??
            (kIsWeb
                ? Uri.base.origin
                : const String.fromEnvironment(
                    'API_BASE_URL',
                    defaultValue: 'http://10.0.2.2:8787',
                  ));
      }
      final uri = Uri.tryParse(server.text.trim());
      if (uri == null ||
          !['https', 'http'].contains(uri.scheme) ||
          uri.host.isEmpty ||
          uri.userInfo.isNotEmpty ||
          uri.query.isNotEmpty ||
          uri.fragment.isNotEmpty) {
        throw Exception('서버 주소를 확인하세요.');
      }
      final response = await http
          .get(
            Uri.parse(
              '${server.text.trim().replaceAll(RegExp(r'/+$'), '')}/api/config',
            ),
          )
          .timeout(const Duration(seconds: 15));
      if (response.statusCode != 200) throw Exception('서버 연결 설정을 확인하세요.');
      final config = jsonDecode(response.body) as Map<String, dynamic>;
      if (config['mode'] == 'local') {
        if (!mounted) return;
        setState(() => local = true);
        return;
      }
      if (config['mode'] != 'supabase') throw Exception('로그인 설정을 확인하세요.');
      if (client == null) {
        await Supabase.initialize(
          url: config['url'] as String,
          publishableKey: config['publishableKey'] as String,
        );
        client = Supabase.instance.client;
        subscription = client!.auth.onAuthStateChange.listen((_) {
          authorize();
        });
      }
      await prefs.setString(
        'api_url',
        server.text.trim().replaceAll(RegExp(r'/+$'), ''),
      );
      await authorize();
    } catch (e) {
      if (mounted) {
        setState(() => error = '서버 또는 로그인 설정을 연결하지 못했습니다. 주소와 네트워크를 확인하세요.');
      }
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  Future<void> authorize() async {
    final id = ++sequence;
    final session = client?.auth.currentSession;
    if (session == null) {
      if (mounted) setState(() => allowed = false);
      return;
    }
    try {
      final value = await client!.rpc('is_app_owner');
      if (mounted && id == sequence) {
        setState(() {
          allowed = value == true;
          error = allowed ? null : '이 앱에 허용된 본인 계정이 아닙니다.';
        });
      }
    } catch (e) {
      if (mounted && id == sequence) {
        setState(() {
          allowed = false;
          error = '계정 접근 권한을 확인하지 못했습니다. 다시 로그인해주세요.';
        });
      }
    }
  }

  Future<void> login() async {
    setState(() {
      busy = true;
      error = null;
    });
    try {
      await client!.auth.signInWithPassword(
        email: email.text.trim(),
        password: password.text,
      );
      password.clear();
      await authorize();
    } on AuthException {
      if (mounted) {
        setState(() => error = '이메일과 비밀번호를 확인하세요. 본인에게 허용된 계정만 로그인할 수 있습니다.');
      }
    } catch (e) {
      if (mounted) setState(() => error = '로그인 연결에 실패했습니다. 다시 시도해주세요.');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (local) return widget.child(null);
    if (allowed && client?.auth.currentSession != null) {
      return Column(
        children: [
          Material(
            child: SafeArea(
              bottom: false,
              child: ListTile(
                dense: true,
                title: const Text('본인 계정으로 로그인됨'),
                trailing: TextButton(
                  onPressed: () async {
                    await client!.auth.signOut();
                  },
                  child: const Text('로그아웃'),
                ),
              ),
            ),
          ),
          Expanded(
            child: widget.child(
              TradingApi(
                server.text.trim().replaceAll(RegExp(r'/+$'), ''),
                '',
                tokenProvider: () =>
                    client!.auth.currentSession?.accessToken ?? '',
              ),
            ),
          ),
        ],
      );
    }
    return Scaffold(
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 450),
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(28),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const Icon(Icons.lock_outline, size: 48),
                const SizedBox(height: 20),
                const Text(
                  '나만의 Trend Lab',
                  textAlign: TextAlign.center,
                  style: TextStyle(fontSize: 28, fontWeight: FontWeight.bold),
                ),
                const SizedBox(height: 12),
                const Text(
                  '본인 계정으로 로그인하면 폰과 PC에서 같은 거래기록을 사용할 수 있습니다.',
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 28),
                if (loading)
                  const LinearProgressIndicator()
                else if (client == null) ...[
                  TextField(
                    controller: server,
                    decoration: const InputDecoration(labelText: '앱 서버 주소'),
                  ),
                  const SizedBox(height: 16),
                  FilledButton(onPressed: load, child: const Text('서버 연결')),
                ] else ...[
                  TextField(
                    controller: email,
                    keyboardType: TextInputType.emailAddress,
                    autofillHints: const [AutofillHints.username],
                    decoration: const InputDecoration(labelText: '본인 이메일'),
                  ),
                  const SizedBox(height: 16),
                  TextField(
                    controller: password,
                    obscureText: true,
                    autofillHints: const [AutofillHints.password],
                    decoration: const InputDecoration(labelText: '비밀번호'),
                    onSubmitted: (_) {
                      if (!busy) login();
                    },
                  ),
                  const SizedBox(height: 20),
                  FilledButton(
                    onPressed: busy ? null : login,
                    child: Text(busy ? '로그인 중…' : '로그인'),
                  ),
                  const SizedBox(height: 12),
                  const Text(
                    '개인용 앱으로 회원가입은 제공하지 않습니다.',
                    textAlign: TextAlign.center,
                    style: TextStyle(fontSize: 12),
                  ),
                ],
                if (error != null)
                  Padding(
                    padding: const EdgeInsets.only(top: 16),
                    child: Text(
                      error!,
                      style: const TextStyle(color: Colors.orangeAccent),
                    ),
                  ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
