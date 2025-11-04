import os
import sys
import subprocess
import platform


def setup_java_home():
    """
    JAVA_HOME 환경변수를 자동으로 설정 (Windows & Linux 지원)
    이미 설정되어 있으면 그대로 사용
    """
    system = platform.system().lower()

    # -----------------------------------------------------------
    # 1️⃣ JAVA_HOME이 이미 존재하면 우선 사용
    # -----------------------------------------------------------
    if 'JAVA_HOME' in os.environ:
        java_home = os.environ['JAVA_HOME']
        jvm_name = 'jvm.dll' if system == 'windows' else 'libjvm.so'
        jvm_path = os.path.join(
            java_home, 'bin' if system == 'windows' else 'lib', 'server', jvm_name
        )
        if os.path.exists(jvm_path):
            return java_home

    # -----------------------------------------------------------
    # 2️⃣ Windows: java -XshowSettings:properties 로 탐색
    # -----------------------------------------------------------
    if system == 'windows':
        try:
            result = subprocess.run(
                'java -XshowSettings:properties',
                shell=True,
                capture_output=True,
                text=True
            )
            output = result.stdout + result.stderr
            for line in output.split('\n'):
                if 'java.home' in line and '=' in line:
                    java_home = line.split('=', 1)[1].strip()
                    jvm_path = os.path.join(java_home, 'bin', 'server', 'jvm.dll')
                    if os.path.exists(jvm_path):
                        os.environ['JAVA_HOME'] = java_home
                        return java_home
        except Exception:
            pass

        # Fallback: where java
        try:
            java_path = subprocess.check_output('where java', shell=True).decode().strip().split('\n')[0]
            java_home = os.path.dirname(os.path.dirname(java_path))
            jvm_path = os.path.join(java_home, 'bin', 'server', 'jvm.dll')
            if os.path.exists(jvm_path):
                os.environ['JAVA_HOME'] = java_home
                return java_home
        except Exception:
            pass

    # -----------------------------------------------------------
    # 3️⃣ Linux: Docker 환경 기본 경로 자동 인식
    # -----------------------------------------------------------
    elif system == 'linux':
        default_home_candidates = [
            '/usr/lib/jvm/java-17-openjdk-amd64',
            '/usr/lib/jvm/java-11-openjdk-amd64'
        ]
        for candidate in default_home_candidates:
            jvm_path = os.path.join(candidate, 'lib', 'server', 'libjvm.so')
            if os.path.exists(jvm_path):
                os.environ['JAVA_HOME'] = candidate
                return candidate

        # java -XshowSettings 방식도 시도
        try:
            result = subprocess.run(
                'java -XshowSettings:properties',
                shell=True,
                capture_output=True,
                text=True
            )
            output = result.stdout + result.stderr
            for line in output.split('\n'):
                if 'java.home' in line and '=' in line:
                    java_home = line.split('=', 1)[1].strip()
                    jvm_path = os.path.join(java_home, 'lib', 'server', 'libjvm.so')
                    if os.path.exists(jvm_path):
                        os.environ['JAVA_HOME'] = java_home
                        return java_home
        except Exception:
            pass

    # -----------------------------------------------------------
    # 4️⃣ 실패 시
    # -----------------------------------------------------------
    raise EnvironmentError(
        "JAVA_HOME 환경변수를 찾을 수 없습니다.\n"
        "Java JDK가 설치되어 있고 libjvm.so 또는 jvm.dll 파일이 존재하는지 확인하세요.\n"
        "Linux Docker의 경우 openjdk-17-jdk 패키지가 포함되어야 합니다."
    )


def init_jpype(jar_path=None):
    """
    JPype 초기화 (JAVA_HOME 설정 + JVM 시작)
    """
    java_home = setup_java_home()

    try:
        import jpype
    except ImportError:
        raise ImportError(
            "JPype1이 설치되어 있지 않습니다.\n"
            "다음 명령으로 설치하세요: pip install JPype1"
        )

    if jpype.isJVMStarted():
        return jpype

    try:
        jvm_path = jpype.getDefaultJVMPath()
        if jar_path:
            jpype.startJVM(jvm_path, f"-Djava.class.path={jar_path}", convertStrings=True)
        else:
            jpype.startJVM(jvm_path, convertStrings=True)
        return jpype
    except Exception as e:
        raise RuntimeError(
            f"JVM 시작 실패: {e}\n"
            f"JAVA_HOME: {java_home}\n"
            f"시스템: {platform.system()} ({platform.machine()})\n"
            "Python과 Java의 비트 버전(32/64bit)이 일치하는지 확인하세요."
        )


def get_java_info():
    """
    현재 Java 환경 정보 반환 (Windows & Linux 모두 지원)
    """
    info = {
        'java_home': os.environ.get('JAVA_HOME', 'Not set'),
        'java_version': None,
        'java_path': None
    }

    try:
        java_version = subprocess.check_output(
            'java -version', stderr=subprocess.STDOUT, shell=True
        ).decode()
        info['java_version'] = java_version.split('\n')[0]
    except Exception:
        info['java_version'] = 'Not found'

    try:
        cmd = 'where java' if platform.system().lower() == 'windows' else 'which java'
        java_path = subprocess.check_output(cmd, shell=True).decode().strip().split('\n')[0]
        info['java_path'] = java_path
    except Exception:
        info['java_path'] = 'Not found'

    return info
