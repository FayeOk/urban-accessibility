import React from 'react';
import { ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import MainPage from './pages/MainPage';
import './styles/App.css';

function App() {
    return (
        <ConfigProvider locale={zhCN}>
            <div className="App">
                <MainPage />
            </div>
        </ConfigProvider>
    );
}

export default App;
