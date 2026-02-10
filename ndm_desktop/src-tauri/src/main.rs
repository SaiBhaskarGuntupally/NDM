use std::fs::{create_dir_all, OpenOptions};
use std::io::Write;
use std::path::PathBuf;
use std::sync::Mutex;
use std::thread;
use std::time::{Duration, Instant};

use tauri::api::process::{Command, CommandChild, CommandEvent};
use tauri::{GlobalShortcutManager, Manager, RunEvent};

const HEALTH_URL: &str = "http://127.0.0.1:8789/health";
const UI_URL: &str = "http://127.0.0.1:8789/ui";

struct BackendState {
    child: Mutex<Option<CommandChild>>,
}

#[tauri::command]
fn enter_kiosk(window: tauri::Window) -> Result<(), String> {
    window
        .set_fullscreen(true)
        .map_err(|err| err.to_string())?;
    window
        .set_decorations(false)
        .map_err(|err| err.to_string())?;
    Ok(())
}

#[tauri::command]
fn exit_kiosk(window: tauri::Window) -> Result<(), String> {
    window
        .set_decorations(true)
        .map_err(|err| err.to_string())?;
    window
        .set_fullscreen(false)
        .map_err(|err| err.to_string())?;
    Ok(())
}

fn spawn_sidecar() -> Option<CommandChild> {
    let command = match Command::new_sidecar("ndm_backend") {
        Ok(command) => command,
        Err(err) => {
            log_line(&format!("sidecar not available: {err}"));
            return None;
        }
    };

    let (mut rx, child) = match command.spawn() {
        Ok(result) => result,
        Err(err) => {
            log_line(&format!("failed to spawn sidecar: {err}"));
            return None;
        }
    };

    tauri::async_runtime::spawn(async move {
        while let Some(event) = rx.recv().await {
            match event {
                CommandEvent::Stdout(line) => log_line(&format!("backend: {line}")),
                CommandEvent::Stderr(line) => log_line(&format!("backend: {line}")),
                _ => {}
            }
        }
    });

    log_line("sidecar spawned successfully");
    Some(child)
}

fn log_line(message: &str) {
    let mut log_path = app_data_dir();
    log_path.push("NDM");
    let _ = create_dir_all(&log_path);
    log_path.push("ndm_desktop.log");

    if let Ok(mut file) = OpenOptions::new().create(true).append(true).open(log_path) {
        let _ = writeln!(file, "{message}");
    }
}

fn app_data_dir() -> PathBuf {
    std::env::var("APPDATA")
        .map(PathBuf::from)
        .unwrap_or_else(|_| PathBuf::from("."))
}

fn wait_for_health(timeout: Duration, interval: Duration) -> bool {
    let start = Instant::now();
    while start.elapsed() < timeout {
        let ok = reqwest::blocking::get(HEALTH_URL)
            .map(|resp| resp.status().is_success())
            .unwrap_or(false);
        if ok {
            return true;
        }
        thread::sleep(interval);
    }
    false
}

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![enter_kiosk, exit_kiosk])
        .manage(BackendState {
            child: Mutex::new(None),
        })
        .setup(|app| {
            let window = app
                .get_window("main")
                .expect("main window must exist");

            // KIOSK MODE
            let window_for_shortcut = window.clone();
            if let Err(err) = app
                .global_shortcut_manager()
                .register("F11", move || {
                    let is_focused = window_for_shortcut.is_focused().unwrap_or(false);
                    if !is_focused {
                        return;
                    }
                    let is_fullscreen = window_for_shortcut
                        .is_fullscreen()
                        .unwrap_or(false);
                    if is_fullscreen {
                        let _ = window_for_shortcut.set_decorations(true);
                        let _ = window_for_shortcut.set_fullscreen(false);
                    } else {
                        let _ = window_for_shortcut.set_fullscreen(true);
                        let _ = window_for_shortcut.set_decorations(false);
                    }
                })
            {
                log_line(&format!("kiosk shortcut registration failed: {err}"));
            }

            let skip_sidecar = std::env::var("NDM_SKIP_SIDECAR")
                .map(|value| value == "1")
                .unwrap_or(false);

            let child = if skip_sidecar { None } else { spawn_sidecar() };
            if let Some(child) = child {
                *app.state::<BackendState>().child.lock().unwrap() = Some(child);
            }

            thread::spawn(move || {
                log_line("waiting for backend health");
                if wait_for_health(Duration::from_millis(15000), Duration::from_millis(150)) {
                    let _ = window.eval(&format!(
                        "window.location.replace('{}')",
                        UI_URL
                    ));
                } else {
                    log_line("backend health check failed");
                    let _ = window.eval(
                        "document.getElementById('status').textContent = 'Backend failed to start. Check logs in %APPDATA%\\NDM\\ndm_backend.log.';",
                    );
                }
            });

            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while running tauri application")
        .run(|app_handle, event| {
            if let RunEvent::ExitRequested { .. } = event {
                let state = app_handle.state::<BackendState>();
                let child = {
                    let mut guard = state.child.lock().unwrap();
                    guard.take()
                };
                if let Some(child) = child {
                    let _ = child.kill();
                }
            }
        });
}
