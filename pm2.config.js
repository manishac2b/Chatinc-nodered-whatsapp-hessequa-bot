module.exports = {
  apps: [
    {
      name: "node-red-bot",
      script: "node-red",
      args: "-s settings.js -u ./",
      watch: false,
      node_args: "--max_old_space_size=1500",
      autorestart: true,
      env: {
        NODE_ENV: "LOCAL",
        /*
        БУДЬ ЛАСКА, ЗРОБІТЬ КОПІЮ ЦЬОГО ФАЙЛА І ДОБАВТЕ ЙОГО В .gitignore .
        ЧЕРЕЗ ДЕЯКИЙ ЧАС Я БУДУ ВИДАЛЯТИ З ТАКИХ ФАЙЛІВ КРЕДИ
        */
      }/*,
      env_dev: {
      }*/
    },
  ],
};
