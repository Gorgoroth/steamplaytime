var app = angular.module('myApp', ['ngDragDrop']);


app.controller('oneCtrl', function($scope, $timeout) {
  $scope.list1 = [];
  $scope.list2 = [];
  $scope.list3 = [];
  $scope.list4 = [];
  
  $scope.list5 = [
    { 'url': 'http://cdn3.steampowered.com/v/gfx/apps/43160/header_292x136.jpg?t=1379520955', name: 'Metro', 'hours': 10, 'drag': true },
    { 'url': 'http://cdn3.steampowered.com/v/gfx/apps/249680/header_292x136.jpg?t=1379697126', name: 'Marlow', 'hours': 10, 'drag': true },
  ];

  // Limit items to be dropped in list1
  $scope.optionsList1 = {
    accept: function(dragEl) {
      if ($scope.list1.length >= 2) {
        return false;
      } else {
        return true;
      }
    }
  };
});

app.controller('GamesCtrl', function($scope) {
  $scope.games = [{'url': "http://cdn3.steampowered.com/v/gfx/apps/43160/header_292x136.jpg?t=1379520955", 'drag': true},
  			{'url': "http://cdn3.steampowered.com/v/gfx/apps/249680/header_292x136.jpg?t=1379520955379697126", 'drag': true}];
  $scope.unbeaten = [];
});