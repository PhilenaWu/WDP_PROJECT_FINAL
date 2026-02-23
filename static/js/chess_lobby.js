(() => {
    // Join the chess lobby socket room on page load
    const socket = window.io ? window.io() : null;

    if (!socket) {
        return;
    }

    // Join the chess lobby when socket connects
    socket.on('connect', () => {
        socket.emit('chess_lobby_join');
    });

    // Listen for lobby updates (invites sent/accepted/declined, games created)
    socket.on('chess_lobby_update', (payload) => {
        if (!payload || !payload.type) {
            return;
        }

        const type = payload.type;

        if (type === 'invite_sent') {
            // An invite was sent to the current user
            reloadLobbySection('incoming');
        } else if (type === 'invite_accepted') {
            // An invite was accepted - refresh all sections
            reloadLobbySection('outgoing');
            reloadLobbySection('active');
        } else if (type === 'invite_declined') {
            // An invite was declined by the other user
            reloadLobbySection('outgoing');
        }
    });

    function reloadLobbySection(section) {
        // Fetch the updated HTML for a lobby section via AJAX
        fetch(`/chess/api/lobby/${section}`)
            .then(res => res.json())
            .then(data => {
                if (data.ok && data.html) {
                    const sectionId = `chess-lobby-${section}`;
                    const sectionEl = document.getElementById(sectionId);
                    if (sectionEl) {
                        sectionEl.innerHTML = data.html;
                    }
                }
            })
            .catch(err => {
                console.error('Failed to reload lobby section:', err);
            });
    }

    // Optional: Auto-refresh lobby every 5 seconds as a fallback
    setInterval(() => {
        if (document.hidden) {
            return;
        }
        fetch('/chess/api/lobby/all')
            .then(res => res.json())
            .then(data => {
                if (data.ok) {
                    updateLobbyUI(data);
                }
            })
            .catch(err => {
                console.error('Failed to refresh lobby:', err);
            });
    }, 5000);

    function updateLobbyUI(data) {
        // Update each section's HTML if it exists
        if (data.incoming_html) {
            const el = document.getElementById('chess-lobby-incoming');
            if (el) el.innerHTML = data.incoming_html;
        }
        if (data.outgoing_html) {
            const el = document.getElementById('chess-lobby-outgoing');
            if (el) el.innerHTML = data.outgoing_html;
        }
        if (data.active_html) {
            const el = document.getElementById('chess-lobby-active');
            if (el) el.innerHTML = data.active_html;
        }
    }
})();
