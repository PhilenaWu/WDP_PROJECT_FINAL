(() => {
    const state = window.CHESS_STATE || {};
    const boardEl = document.getElementById('chess-board');
    const statusEl = document.getElementById('chess-status');
    const movesEl = document.getElementById('chess-moves');
    const infoEl = document.getElementById('chess-info');

    if (!boardEl) {
        return;
    }

    const files = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'];
    const ranks = ['8', '7', '6', '5', '4', '3', '2', '1'];

    let selectedSquare = null;
    let legalTargets = new Set();
    let currentBoard = {};

    const socket = window.io ? window.io() : null;

    if (socket && state.gameId) {
        socket.on('connect', () => {
            socket.emit('chess_join', { game_id: state.gameId });
        });

        socket.on('chess_update', (payload) => {
            if (!payload || payload.game_id !== state.gameId) {
                return;
            }
            applyUpdate(payload);
        });

        socket.on('chess_error', (payload) => {
            if (payload && payload.message) {
                setStatus(payload.message);
            }
        });
    }

    function setStatus(message) {
        if (statusEl) {
            statusEl.textContent = message || '';
        }
    }

    function setInfo(message) {
        if (infoEl) {
            infoEl.textContent = message || '';
        }
    }

    function parseFen(fen) {
        const map = {};
        if (!fen) {
            return map;
        }
        const placement = fen.split(' ')[0];
        const rows = placement.split('/');
        for (let r = 0; r < 8; r += 1) {
            const row = rows[r];
            let fileIndex = 0;
            for (const char of row) {
                if (Number.isInteger(Number(char))) {
                    fileIndex += Number(char);
                } else {
                    const square = `${files[fileIndex]}${ranks[r]}`;
                    map[square] = char;
                    fileIndex += 1;
                }
            }
        }
        return map;
    }

    function isOwnPiece(piece) {
        if (!piece) {
            return false;
        }
        if (state.playerColor === 'white') {
            return piece === piece.toUpperCase();
        }
        return piece === piece.toLowerCase();
    }

    function pieceText(piece) {
        if (!piece) {
            return '';
        }
        const pieceMap = {
            K: '♔',
            Q: '♕',
            R: '♖',
            B: '♗',
            N: '♘',
            P: '♙',
            k: '♚',
            q: '♛',
            r: '♜',
            b: '♝',
            n: '♞',
            p: '♟'
        };
        return pieceMap[piece] || piece.toUpperCase();
    }

    function pieceClass(piece) {
        if (!piece) {
            return '';
        }
        return piece === piece.toUpperCase() ? 'white' : 'black';
    }

    function clearSelection() {
        selectedSquare = null;
        legalTargets = new Set();
        renderBoard();
    }

    function squareColor(fileIndex, rankIndex) {
        return (fileIndex + rankIndex) % 2 === 0 ? 'light' : 'dark';
    }

    function renderBoard() {
        currentBoard = parseFen(state.fen);
        boardEl.innerHTML = '';

        const fileOrder = state.orientation === 'black' ? [...files].reverse() : files;
        const rankOrder = state.orientation === 'black' ? [...ranks].reverse() : ranks;

        for (let r = 0; r < rankOrder.length; r += 1) {
            for (let f = 0; f < fileOrder.length; f += 1) {
                const square = `${fileOrder[f]}${rankOrder[r]}`;
                const piece = currentBoard[square];
                const squareEl = document.createElement('div');

                squareEl.className = `chess-square ${squareColor(f, r)}`;
                squareEl.dataset.square = square;

                if (selectedSquare === square) {
                    squareEl.classList.add('selected');
                }
                if (legalTargets.has(square)) {
                    squareEl.classList.add('legal');
                }

                if (piece) {
                    const pieceEl = document.createElement('span');
                    pieceEl.className = `chess-piece ${pieceClass(piece)}`;
                    pieceEl.textContent = pieceText(piece);
                    squareEl.appendChild(pieceEl);
                }

                if (legalTargets.has(square)) {
                    const isCapture = piece && !isOwnPiece(piece);
                    if (isCapture) {
                        squareEl.classList.add('capture');
                        const ring = document.createElement('span');
                        ring.className = 'capture-ring';
                        squareEl.appendChild(ring);
                    } else {
                        const dot = document.createElement('span');
                        dot.className = 'move-dot';
                        squareEl.appendChild(dot);
                    }
                }

                squareEl.addEventListener('click', () => handleSquareClick(square));
                boardEl.appendChild(squareEl);
            }
        }
    }

    function updateMoves(moves) {
        if (!movesEl) {
            return;
        }
        movesEl.innerHTML = '';
        (moves || []).forEach((move, idx) => {
            const li = document.createElement('li');
            const moveNumber = Math.floor(idx / 2) + 1;
            const prefix = idx % 2 === 0 ? `${moveNumber}. ` : '... ';
            li.textContent = `${prefix}${move}`;
            movesEl.appendChild(li);
        });
    }

    function handleSquareClick(square) {
        if (state.status !== 'active') {
            setStatus('Game is not active.');
            return;
        }
        if (state.turn !== state.playerColor) {
            setStatus('Waiting for your opponent.');
            return;
        }

        const piece = currentBoard[square];
        if (selectedSquare) {
            if (square === selectedSquare) {
                clearSelection();
                return;
            }

            if (legalTargets.has(square)) {
                submitMove(selectedSquare, square);
                return;
            }

            if (piece && isOwnPiece(piece)) {
                selectSquare(square);
                return;
            }

            clearSelection();
            return;
        }

        if (piece && isOwnPiece(piece)) {
            selectSquare(square);
        }
    }

    function selectSquare(square) {
        selectedSquare = square;
        fetchLegalMoves(square);
    }

    function fetchLegalMoves(square) {
        fetch('/chess/api/legal', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ game_id: state.gameId, square })
        })
            .then((res) => res.json())
            .then((payload) => {
                if (!payload.ok) {
                    setStatus(payload.message || 'Unable to fetch moves.');
                    clearSelection();
                    return;
                }
                legalTargets = new Set(payload.targets || []);
                renderBoard();
            })
            .catch(() => {
                setStatus('Unable to fetch legal moves.');
                clearSelection();
            });
    }

    function submitMove(fromSq, toSq) {
        fetch('/chess/api/move', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ game_id: state.gameId, from: fromSq, to: toSq })
        })
            .then((res) => res.json())
            .then((payload) => {
                if (!payload.ok) {
                    setStatus(payload.message || 'Move rejected.');
                    return;
                }
                applyUpdate(payload);
            })
            .catch(() => {
                setStatus('Move failed. Try again.');
            })
            .finally(() => {
                selectedSquare = null;
                legalTargets = new Set();
            });
    }

    function applyUpdate(payload) {
        state.fen = payload.fen;
        state.moves = payload.moves || [];
        state.status = payload.status;
        state.result = payload.result || null;
        state.turn = payload.turn || state.turn;

        renderBoard();
        updateMoves(state.moves);

        let statusMsg = '';
        if (payload.message) {
            statusMsg = payload.message;
        } else if (state.status === 'finished') {
            if (state.result === 'draw') {
                statusMsg = 'Game over: Draw.';
            } else if (state.result) {
                statusMsg = `Game over: ${state.result} wins.`;
            } else {
                statusMsg = 'Game over.';
            }
        } else {
            statusMsg = state.turn === state.playerColor ? 'Your move.' : 'Opponent turn.';
        }
        setStatus(statusMsg);

        // Show toast for forfeit
        if (payload.message && payload.message.includes('forfeited')) {
            showToast(payload.message, 'success');
        }
    }

    function showToast(message, type = 'info') {
        const toastContainer = document.getElementById('chess-toast-container') || (() => {
            const container = document.createElement('div');
            container.id = 'chess-toast-container';
            container.style.cssText = 'position: fixed; top: 20px; right: 20px; z-index: 9999; display: flex; flex-direction: column; gap: 10px;';
            document.body.appendChild(container);
            return container;
        })();

        const toast = document.createElement('div');
        toast.className = `alert alert-${type === 'success' ? 'success' : 'info'} alert-dismissible fade show`;
        toast.style.cssText = 'min-width: 280px; box-shadow: 0 4px 12px rgba(0,0,0,0.15);';
        toast.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        `;
        toastContainer.appendChild(toast);

        setTimeout(() => {
            toast.remove();
        }, 4000);
    }

    function init() {
        renderBoard();
        updateMoves(state.moves || []);
        setInfo(`You are playing as ${state.playerColor}.`);
        setStatus(state.turn === state.playerColor ? 'Your move.' : 'Opponent turn.');
    }

    init();
})();
