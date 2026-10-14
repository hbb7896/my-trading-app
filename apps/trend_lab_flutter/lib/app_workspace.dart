import 'package:flutter/material.dart';

import 'api.dart';
import 'main.dart' show JournalScreen;
import 'trading_master.dart';

/// Both workspaces use the same authenticated API and trade collection.
class AppWorkspace extends StatefulWidget {
  final TradingApi? api;
  const AppWorkspace({super.key, this.api});
  @override
  State<AppWorkspace> createState() => _AppWorkspaceState();
}

class _AppWorkspaceState extends State<AppWorkspace> {
  int selected = 0;
  @override
  Widget build(BuildContext context) => Scaffold(
    body: selected == 0
        ? JournalScreen(initialApi: widget.api)
        : TradingMasterScreen(api: widget.api),
    bottomNavigationBar: NavigationBar(
      selectedIndex: selected,
      onDestinationSelected: (value) => setState(() => selected = value),
      destinations: const [
        NavigationDestination(icon: Icon(Icons.show_chart), label: '트렌드랩'),
        NavigationDestination(icon: Icon(Icons.insights), label: '트레이딩 마스터'),
      ],
    ),
  );
}
