require('dotenv').config();
const express = require('express');
const mongoose = require('mongoose');
const cors = require('cors');
const http = require('http');
const { Server } = require('socket.io');
const path = require('path');
const multer = require('multer');
const fs = require('fs');

// Models
const User = require('./models/User');
const Order = require('./models/Order');

const app = express();
const server = http.createServer(app);
const io = new Server(server, { cors: { origin: "*" } });

// Middleware
app.use(cors());
app.use(express.json());
app.use('/web', express.static(path.join(__dirname, 'web')));
app.use('/uploads', express.static(path.join(__dirname, 'uploads')));

// File Upload
const storage = multer.diskStorage({
    destination: (req, file, cb) => cb(null, './uploads/checks'),
    filename: (req, file, cb) => cb(null, Date.now() + '-' + file.originalname)
});
const upload = multer({ storage });

// MongoDB
mongoose.connect(process.env.MONGODB_URI)
    .then(() => console.log('✅ MongoDB connected'))
    .catch(err => console.error('❌ MongoDB error:', err));

// --- API ROUTES ---

const bcrypt = require('bcryptjs');

// Admin Auth
app.post('/api/auth/login', async (req, res) => {
    const { username, password } = req.body;

    // Default admin from ENV (for first time)
    if (username === 'admin' && password === process.env.ADMIN_PASSWORD) {
        return res.json({ success: true, role: 'admin' });
    }

    // Check Users in DB
    const user = await User.findOne({ username, role: 'admin' });
    if (user && await bcrypt.compare(password, user.password)) {
        return res.json({ success: true, role: 'admin', user });
    }
    res.status(401).json({ success: false, message: 'Login yoki parol xato!' });
});

// Get Employees sorted by rating
app.get('/api/employees', async (req, res) => {
    const employees = await User.find({ role: 'employee' }).sort({ averageRating: -1, totalOrders: -1 });
    res.json(employees);
});

// Get Pending Orders
app.get('/api/orders/pending', async (req, res) => {
    const orders = await Order.find({ status: 'pending' }).sort({ 'timestamps.created': -1 });
    res.json(orders);
});

// Get Active Orders (Assigned or Ready)
app.get('/api/orders/active', async (req, res) => {
    const orders = await Order.find({ status: { $in: ['assigned', 'ready'] } }).populate('employee').sort({ 'timestamps.created': -1 });
    res.json(orders);
});

// Update Employee Profile (Set as employee)
app.post('/api/employees/register', async (req, res) => {
    const { telegramId, firstName, lastName, phone } = req.body;
    let user = await User.findOne({ telegramId });
    if (!user) user = new User({ telegramId });

    user.firstName = firstName;
    user.lastName = lastName;
    user.phone = phone;
    user.role = 'employee';
    await user.save();
    res.json({ success: true, user });
});

// --- BOT INTEGRATION ---
const bot = require('./bot/index');

// Assign Order
app.post('/api/orders/:id/assign', async (req, res) => {
    try {
        const { employeeId, price } = req.body;
        const order = await Order.findById(req.params.id);
        const employee = await User.findById(employeeId);

        if (!order || !employee) return res.status(404).json({ success: false, message: 'Topilmadi' });

        order.employee = employeeId;
        order.details.price = price;
        order.status = 'assigned';
        order.timestamps.assigned = new Date();
        await order.save();

        // Notify Employee via Bot
        const msg = `🆕 Yangi buyurtma biriktirildi!\n📍 Qayerdan: ${order.details.from}\n🏁 Qayerga: ${order.details.to}\n💰 Narxi: ${price} so'm\n📝 Izoh: ${order.details.description || 'Yo\'q'}`;

        const inline_keyboard = {
            inline_keyboard: [
                [{ text: "🚀 Tayyor (Ready)", callback_data: `ready_${order._id}` }],
                [{ text: "✅ Tugatildi (Complete)", callback_data: `complete_${order._id}` }]
            ]
        };

        bot.sendMessage(employee.telegramId, msg, { reply_markup: inline_keyboard });

        io.emit('order_updated', order);
        res.json({ success: true, order });
    } catch (e) { res.status(500).json({ success: false, error: e.message }); }
});

// Get Orders for Analytics
app.get('/api/analytics/orders', async (req, res) => {
    const stats = await User.aggregate([
        { $match: { role: 'employee' } },
        { $project: { firstName: 1, lastName: 1, totalOrders: 1, averageRating: 1 } }
    ]);
    res.json(stats);
});

// Health check / Keep-alive ping
app.get('/api/ping', (req, res) => res.json({ status: 'alive', time: new Date() }));

// Get Analytics Summary
app.get('/api/analytics/summary', async (req, res) => {
    const totalOrders = await Order.countDocuments();
    const completedOrders = await Order.countDocuments({ status: 'completed' });
    const employees = await User.find({ role: 'employee' });
    const avgRating = employees.length > 0 ? (employees.reduce((a, b) => a + b.averageRating, 0) / employees.length).toFixed(1) : 0;

    // Simple revenue calculation (sum of all completed orders' prices)
    const revenueData = await Order.aggregate([
        { $match: { status: 'completed' } },
        { $group: { _id: null, total: { $sum: "$details.price" } } }
    ]);
    const revenue = revenueData.length > 0 ? revenueData[0].total : 0;

    res.json({ totalOrders, completedOrders, avgRating, revenue, activeEmployees: employees.length });
});

// Root redirect
app.get('/', (req, res) => res.redirect('/web'));

// --- SOCKETS ---
io.on('connection', (socket) => {
    console.log('User connected:', socket.id);
    socket.on('disconnect', () => console.log('User disconnected'));
});

const PORT = process.env.PORT || 5000;
server.listen(PORT, () => console.log(`🚀 Server running on port ${PORT}`));

// Export for bot
module.exports = { app, server, io };
