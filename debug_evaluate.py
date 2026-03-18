"""
调试评估报告功能的测试脚本
"""
import requests
import json

API_BASE_URL = "http://localhost:8000"

def test_evaluation_debug():
    """测试评估报告功能 - 调试版本"""
    print("开始测试评估报告功能（调试模式）...")
    
    # 使用之前创建的学生和提交
    submission_id = "SUB_C0592DB9"
    
    # 测试数据
    test_data = {
        "submission_id": submission_id
    }
    
    try:
        # 发送评估请求
        print(f"发送评估请求到: {API_BASE_URL}/evaluate")
        print(f"请求数据: {json.dumps(test_data, ensure_ascii=False)}")
        
        response = requests.post(
            f"{API_BASE_URL}/evaluate",
            json=test_data,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        # 打印响应
        print(f"响应状态码: {response.status_code}")
        print(f"响应头: {dict(response.headers)}")
        
        try:
            # 尝试解析JSON响应
            response_json = response.json()
            print(f"响应内容: {json.dumps(response_json, ensure_ascii=False, indent=2)}")
        except Exception as e:
            # 如果不是JSON响应，直接打印内容
            print(f"响应内容: {response.text}")
            print(f"解析JSON失败: {str(e)}")
        
        if response.status_code == 200:
            print("评估报告功能测试成功！")
            return True
        else:
            print("评估报告功能测试失败！")
            return False
            
    except requests.exceptions.ConnectionError as e:
        print(f"连接错误: 无法连接到服务器。请确保后端服务正在运行。")
        print(f"详细错误: {str(e)}")
        return False
    except requests.exceptions.Timeout as e:
        print(f"超时错误: 请求超时。")
        print(f"详细错误: {str(e)}")
        return False
    except Exception as e:
        print(f"测试过程中出错: {str(e)}")
        import traceback
        print(f"详细错误: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    test_evaluation_debug()
