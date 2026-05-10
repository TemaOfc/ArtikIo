class DrawingCanvas {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        this.ctx = this.canvas.getContext('2d');
        this.isDrawing = false;
        this.isEnabled = false;
        this.currentTool = 'brush';
        this.currentColor = '#000000';
        this.brushSize = 5;
        this.startX = 0;
        this.startY = 0;
        this.history = [];
        this.historyStep = -1;
        this.lastSnapshotTime = 0;
        this.snapshotInterval = 2000; // Отправлять снимок каждые 2 секунды

        this.setupCanvas();
        this.setupEventListeners();
        this.clearCanvas();
    }

    setupCanvas() {
        const container = this.canvas.parentElement;
        const updateCanvasSize = () => {
            const containerWidth = container.clientWidth - 20;
            const containerHeight = container.clientHeight - 20;

            const baseWidth = 800;
            const baseHeight = 600;
            const aspectRatio = baseWidth / baseHeight;

            let newWidth, newHeight;

            if (containerWidth / containerHeight > aspectRatio) {
                newHeight = containerHeight;
                newWidth = newHeight * aspectRatio;
            } else {
                newWidth = containerWidth;
                newHeight = newWidth / aspectRatio;
            }

            this.canvas.style.width = newWidth + 'px';
            this.canvas.style.height = newHeight + 'px';
        };

        updateCanvasSize();
        window.addEventListener('resize', updateCanvasSize);
        window.addEventListener('orientationchange', () => {
            setTimeout(updateCanvasSize, 100);
        });
    }

    setupEventListeners() {
        this.canvas.addEventListener('mousedown', (e) => this.startDrawing(e));
        this.canvas.addEventListener('mousemove', (e) => this.draw(e));
        this.canvas.addEventListener('mouseup', () => this.stopDrawing());
        this.canvas.addEventListener('mouseleave', () => this.stopDrawing());

        this.canvas.addEventListener('touchstart', (e) => {
            e.preventDefault();
            const touch = e.touches[0];
            const mouseEvent = new MouseEvent('mousedown', {
                clientX: touch.clientX,
                clientY: touch.clientY
            });
            this.canvas.dispatchEvent(mouseEvent);
        });

        this.canvas.addEventListener('touchmove', (e) => {
            e.preventDefault();
            const touch = e.touches[0];
            const mouseEvent = new MouseEvent('mousemove', {
                clientX: touch.clientX,
                clientY: touch.clientY
            });
            this.canvas.dispatchEvent(mouseEvent);
        });

        this.canvas.addEventListener('touchend', (e) => {
            e.preventDefault();
            const mouseEvent = new MouseEvent('mouseup', {});
            this.canvas.dispatchEvent(mouseEvent);
        });
    }

    getMousePos(e) {
        const rect = this.canvas.getBoundingClientRect();
        const scaleX = this.canvas.width / rect.width;
        const scaleY = this.canvas.height / rect.height;

        return {
            x: (e.clientX - rect.left) * scaleX,
            y: (e.clientY - rect.top) * scaleY
        };
    }

    startDrawing(e) {
        if (!this.isEnabled) return;

        this.isDrawing = true;
        const pos = this.getMousePos(e);
        this.startX = pos.x;
        this.startY = pos.y;
        this.lastX = pos.x;
        this.lastY = pos.y;

        if (this.currentTool === 'brush') {
            this.ctx.globalCompositeOperation = 'source-over';
            this.ctx.beginPath();
            this.ctx.moveTo(pos.x, pos.y);
        } else if (this.currentTool === 'eraser') {
            this.ctx.globalCompositeOperation = 'destination-out';
            this.ctx.beginPath();
            this.ctx.moveTo(pos.x, pos.y);
        } else if (this.currentTool === 'fill') {
            this.ctx.globalCompositeOperation = 'source-over';
            this.floodFill(Math.floor(pos.x), Math.floor(pos.y), this.currentColor);
            this.isDrawing = false;
            this.saveState();
            this.emitAction({
                tool: 'fill',
                x: Math.floor(pos.x),
                y: Math.floor(pos.y),
                color: this.currentColor
            });
        }
    }

    draw(e) {
        if (!this.isDrawing || !this.isEnabled) return;

        const pos = this.getMousePos(e);

        if (this.currentTool === 'brush') {
            this.ctx.globalCompositeOperation = 'source-over';
            this.ctx.strokeStyle = this.currentColor;
            this.ctx.lineWidth = this.brushSize;
            this.ctx.lineCap = 'round';
            this.ctx.lineJoin = 'round';
            this.ctx.lineTo(pos.x, pos.y);
            this.ctx.stroke();

            this.emitAction({
                tool: 'brush',
                x: pos.x,
                y: pos.y,
                color: this.currentColor,
                size: this.brushSize,
                startX: this.lastX || pos.x,
                startY: this.lastY || pos.y
            });

            this.lastX = pos.x;
            this.lastY = pos.y;
        } else if (this.currentTool === 'eraser') {
            this.ctx.globalCompositeOperation = 'destination-out';
            this.ctx.strokeStyle = 'rgba(0,0,0,1)';
            this.ctx.lineWidth = this.brushSize;
            this.ctx.lineCap = 'round';
            this.ctx.lineJoin = 'round';
            this.ctx.lineTo(pos.x, pos.y);
            this.ctx.stroke();
            this.ctx.globalCompositeOperation = 'source-over';

            this.emitAction({
                tool: 'eraser',
                x: pos.x,
                y: pos.y,
                size: this.brushSize,
                startX: this.lastX || pos.x,
                startY: this.lastY || pos.y
            });

            this.lastX = pos.x;
            this.lastY = pos.y;
        }
    }

    stopDrawing() {
        if (!this.isDrawing) return;

        if (this.currentTool === 'line' || this.currentTool === 'rect' || this.currentTool === 'circle') {
            const pos = this.getMousePos(event);
            this.drawShape(this.startX, this.startY, pos.x, pos.y);
        }

        if (this.isDrawing && (this.currentTool === 'brush' || this.currentTool === 'eraser' ||
            this.currentTool === 'line' || this.currentTool === 'rect' || this.currentTool === 'circle')) {
            this.saveState();
        }

        // Отправить событие окончания рисования
        if (this.currentTool === 'brush' || this.currentTool === 'eraser') {
            this.emitAction({
                tool: 'path_end'
            });
        }

        this.isDrawing = false;
        this.ctx.beginPath();
        this.ctx.globalCompositeOperation = 'source-over';
        this.lastX = null;
        this.lastY = null;
    }

    drawShape(startX, startY, endX, endY) {
        this.ctx.strokeStyle = this.currentColor;
        this.ctx.lineWidth = this.brushSize;
        this.ctx.lineCap = 'round';

        if (this.currentTool === 'line') {
            this.ctx.beginPath();
            this.ctx.moveTo(startX, startY);
            this.ctx.lineTo(endX, endY);
            this.ctx.stroke();

            this.emitAction({
                tool: 'line',
                startX, startY, endX, endY,
                color: this.currentColor,
                size: this.brushSize
            });
        } else if (this.currentTool === 'rect') {
            const width = endX - startX;
            const height = endY - startY;
            this.ctx.strokeRect(startX, startY, width, height);

            this.emitAction({
                tool: 'rect',
                startX, startY,
                width, height,
                color: this.currentColor,
                size: this.brushSize
            });
        } else if (this.currentTool === 'circle') {
            const radius = Math.sqrt(Math.pow(endX - startX, 2) + Math.pow(endY - startY, 2));
            this.ctx.beginPath();
            this.ctx.arc(startX, startY, radius, 0, 2 * Math.PI);
            this.ctx.stroke();

            this.emitAction({
                tool: 'circle',
                centerX: startX,
                centerY: startY,
                radius,
                color: this.currentColor,
                size: this.brushSize
            });
        }
    }

    floodFill(x, y, fillColor) {
        const imageData = this.ctx.getImageData(0, 0, this.canvas.width, this.canvas.height);
        const targetColor = this.getPixelColor(imageData, x, y);
        const fillColorRgb = this.hexToRgb(fillColor);

        if (this.colorsMatch(targetColor, fillColorRgb)) return;

        const stack = [[x, y]];
        const visited = new Set();

        while (stack.length > 0) {
            const [currentX, currentY] = stack.pop();
            const key = `${currentX},${currentY}`;

            if (visited.has(key)) continue;
            if (currentX < 0 || currentX >= this.canvas.width || currentY < 0 || currentY >= this.canvas.height) continue;

            const currentColor = this.getPixelColor(imageData, currentX, currentY);
            if (!this.colorsMatch(currentColor, targetColor)) continue;

            this.setPixelColor(imageData, currentX, currentY, fillColorRgb);
            visited.add(key);

            stack.push([currentX + 1, currentY]);
            stack.push([currentX - 1, currentY]);
            stack.push([currentX, currentY + 1]);
            stack.push([currentX, currentY - 1]);
        }

        this.ctx.putImageData(imageData, 0, 0);
    }

    getPixelColor(imageData, x, y) {
        const index = (y * imageData.width + x) * 4;
        return {
            r: imageData.data[index],
            g: imageData.data[index + 1],
            b: imageData.data[index + 2],
            a: imageData.data[index + 3]
        };
    }

    setPixelColor(imageData, x, y, color) {
        const index = (y * imageData.width + x) * 4;
        imageData.data[index] = color.r;
        imageData.data[index + 1] = color.g;
        imageData.data[index + 2] = color.b;
        imageData.data[index + 3] = 255;
    }

    colorsMatch(c1, c2) {
        return c1.r === c2.r && c1.g === c2.g && c1.b === c2.b && c1.a === c2.a;
    }

    hexToRgb(hex) {
        const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
        return result ? {
            r: parseInt(result[1], 16),
            g: parseInt(result[2], 16),
            b: parseInt(result[3], 16),
            a: 255
        } : { r: 0, g: 0, b: 0, a: 255 };
    }

    applyAction(action) {
        if (action.tool === 'path_end') {
            // Сбросить временный путь
            this.ctx.beginPath();
            this.ctx.globalCompositeOperation = 'source-over';
            this.tempPath = null;
            return;
        }

        if (action.tool === 'brush') {
            if (!this.tempPath || this.tempPath.tool !== 'brush' || this.tempPath.color !== action.color || this.tempPath.size !== action.size) {
                this.ctx.globalCompositeOperation = 'source-over';
                this.ctx.beginPath();
                this.ctx.moveTo(action.startX || action.x, action.startY || action.y);
                this.tempPath = { tool: 'brush', color: action.color, size: action.size };
            }
            this.ctx.globalCompositeOperation = 'source-over';
            this.ctx.strokeStyle = action.color;
            this.ctx.lineWidth = action.size;
            this.ctx.lineCap = 'round';
            this.ctx.lineJoin = 'round';
            this.ctx.lineTo(action.x, action.y);
            this.ctx.stroke();
        } else if (action.tool === 'eraser') {
            if (!this.tempPath || this.tempPath.tool !== 'eraser' || this.tempPath.size !== action.size) {
                this.ctx.globalCompositeOperation = 'destination-out';
                this.ctx.beginPath();
                this.ctx.moveTo(action.startX || action.x, action.startY || action.y);
                this.tempPath = { tool: 'eraser', size: action.size };
            }
            this.ctx.globalCompositeOperation = 'destination-out';
            this.ctx.strokeStyle = 'rgba(0,0,0,1)';
            this.ctx.lineWidth = action.size;
            this.ctx.lineCap = 'round';
            this.ctx.lineJoin = 'round';
            this.ctx.lineTo(action.x, action.y);
            this.ctx.stroke();
            this.ctx.globalCompositeOperation = 'source-over';
        } else if (action.tool === 'line') {
            this.ctx.globalCompositeOperation = 'source-over';
            this.ctx.strokeStyle = action.color;
            this.ctx.lineWidth = action.size;
            this.ctx.beginPath();
            this.ctx.moveTo(action.startX, action.startY);
            this.ctx.lineTo(action.endX, action.endY);
            this.ctx.stroke();
            this.tempPath = null;
        } else if (action.tool === 'rect') {
            this.ctx.globalCompositeOperation = 'source-over';
            this.ctx.strokeStyle = action.color;
            this.ctx.lineWidth = action.size;
            this.ctx.strokeRect(action.startX, action.startY, action.width, action.height);
            this.tempPath = null;
        } else if (action.tool === 'circle') {
            this.ctx.globalCompositeOperation = 'source-over';
            this.ctx.strokeStyle = action.color;
            this.ctx.lineWidth = action.size;
            this.ctx.beginPath();
            this.ctx.arc(action.centerX, action.centerY, action.radius, 0, 2 * Math.PI);
            this.ctx.stroke();
            this.tempPath = null;
        } else if (action.tool === 'fill') {
            this.ctx.globalCompositeOperation = 'source-over';
            this.floodFill(action.x, action.y, action.color);
            this.tempPath = null;
        }
    }

    setTool(tool) {
        this.currentTool = tool;
    }

    setColor(color) {
        this.currentColor = color;
    }

    setBrushSize(size) {
        this.brushSize = size;
    }

    setEnabled(enabled) {
        this.isEnabled = enabled;
        this.canvas.classList.toggle('disabled', !enabled);
    }

    clearCanvas() {
        this.ctx.fillStyle = '#FFFFFF';
        this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
        this.history = [];
        this.historyStep = -1;
        this.tempPath = null;
    }

    saveState() {
        this.historyStep++;
        if (this.historyStep < this.history.length) {
            this.history.length = this.historyStep;
        }
        this.history.push(this.canvas.toDataURL());
    }

    undo() {
        if (this.historyStep > 0) {
            this.historyStep--;
            const img = new Image();
            img.src = this.history[this.historyStep];
            img.onload = () => {
                this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
                this.ctx.drawImage(img, 0, 0);
            };
        }
    }

    emitAction(action) {
        if (window.gameSocket && this.isEnabled) {
            window.gameSocket.emitDrawAction(action);
            this.sendSnapshotIfNeeded();
        }
    }

    sendSnapshotIfNeeded() {
        const now = Date.now();
        if (now - this.lastSnapshotTime > this.snapshotInterval) {
            this.sendSnapshot();
            this.lastSnapshotTime = now;
        }
    }

    sendSnapshot() {
        if (window.gameSocket && this.isEnabled) {
            const snapshot = this.canvas.toDataURL('image/png');
            window.gameSocket.sendCanvasSnapshot(snapshot);
        }
    }

    loadSnapshot(snapshot) {
        const img = new Image();
        img.onload = () => {
            this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
            this.ctx.drawImage(img, 0, 0);
        };
        img.src = snapshot;
    }
}
